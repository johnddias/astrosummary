
from __future__ import annotations
import re
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Iterable

# =======================================================
# NINA Session Analyzer (regenerated)
# - Robust timestamp parsing
# - Clear categories with precedence
# - Idle waits (dark/altitude/safe) separated from productive time
# - Combined Slew+Solve+Center(+PHD settle) overhead
# - Exposure + download gap estimation
# - Merges adjacent segments; portable CLI and FastAPI API
# =======================================================

# Timestamp + message capture
TS_RE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)\|[A-Z]+\|[^|]*\|[^|]*\|\d+\|(?P<msg>.*)$'
)


def _parse_iso_ts(s: str) -> datetime:
    """Parse ISO timestamp strings that may have non-standard fractional second widths.

    Python's datetime.fromisoformat expects up to 6 fractional digits (microseconds).
    Some logs contain 3-5 fractional digits or other widths; normalize by padding or
    truncating to 6 digits before parsing.
    """
    if '.' not in s:
        return datetime.fromisoformat(s)
    datepart, frac = s.split('.', 1)
    # strip timezone if present (we don't expect it in these logs)
    frac = re.sub(r'[^0-9].*$', '', frac)
    if len(frac) > 6:
        frac = frac[:6]
    else:
        frac = frac.ljust(6, '0')
    normalized = f"{datepart}.{frac}"
    return datetime.fromisoformat(normalized)

# Key patterns
PAT = {
    # Focus
    "start_autofocus": re.compile(r'\bStarting Category:\s*Focuser,\s*Item:\s*RunAutofocus\b'),
    "done_autofocus": re.compile(r'\bAutoFocus completed\b'),

    # Slew / solve / center
    "start_slew": re.compile(r'TelescopeVM\.cs\|SlewToCoordinatesAsync'),
    "solve_begin": re.compile(r'ImageSolver\.cs\|Solve\|41\|Platesolving'),
    "solve_success": re.compile(r'\bPlatesolve successful\b'),
    "center_finish": re.compile(r'\bFinishing Category:\s*Telescope,\s*Item:\s*Center\b'),
    "sync": re.compile(r'\bTelescopeVM\.cs\|Sync\b'),

    # PHD settle
    "phd_settle_begin": re.compile(r'\bStarting Category:\s*Phd2 Tools,\s*Item:\s*Phd2SettleInstruction\b'),
    "phd_settle_end": re.compile(r'\bFinishing Category:\s*Phd2 Tools,\s*Item:\s*Phd2SettleInstruction\b'),

    # Idle waits (intentional)
    "wait_time_begin": re.compile(r'\bStarting Category:\s*Utility,\s*Item:\s*WaitForTime\b'),
    "wait_alt_begin": re.compile(r'\bStarting Category:\s*Utility,\s*Item:\s*WaitForAltitude\b'),
    "wait_safe_begin": re.compile(r'\bStarting Category:\s*Safety Monitor,\s*Item:\s*WaitUntilSafe\b'),
    "wait_generic_end": re.compile(r'\bFinishing Category:\s*(Utility|Safety Monitor),'),

    # Captures
    "capture_begin": re.compile(r'\bStarting Exposure - Exposure Time:\s*(?P<exp>[0-9]+(?:\.[0-9]+)?)s\b'),

    # Flip
    "flip_notice": re.compile(r'\bMeridian Flip\b'),
    "flip_start": re.compile(r'\bMeridian Flip.*(Starting|initiated)\b', re.IGNORECASE),
    "flip_done": re.compile(r'\bMeridian Flip.*(completed|finished)\b', re.IGNORECASE),
}

@dataclass
class Segment:
    start: datetime
    end: datetime
    label: str
    meta: Dict[str, str]

    @property
    def duration_s(self) -> float:
        return max(0.0, (self.end - self.start).total_seconds())

def _accumulate(seglist: List[Segment], start: datetime, end: datetime, label: str, **meta):
    if end <= start:
        return
    seglist.append(Segment(start, end, label, {k: str(v) for k, v in meta.items()}))

def _merge_adjacent(segments: List[Segment], join_window_s: float = 2.0) -> List[Segment]:
    if not segments:
        return []
    segments = sorted(segments, key=lambda s: (s.start, s.end))
    merged: List[Segment] = [segments[0]]
    for seg in segments[1:]:
        last = merged[-1]
        if last.label == seg.label and (seg.start - last.end).total_seconds() <= join_window_s:
            last.end = max(last.end, seg.end)
            # merge meta if helpful (keep earliest)
        else:
            merged.append(seg)
    return merged

def parse_nina_log(
    text: str,
    download_gap_cap_s: float = 20.0,
    join_window_s: float = 2.0
) -> Dict[str, object]:
    """
    Parse a NINA log and produce a categorized session model.

    Returns:
    {
      "totals_seconds": {label: seconds, ...},
      "productive_seconds": float,
      "idle_seconds": float,
      "segments": [{start, end, label, meta}, ...]
    }
    """
    # Collect (timestamp, message)
    events: List[Tuple[datetime, str]] = []
    for ln in text.splitlines():
        m = TS_RE.match(ln)
        if not m:
            continue
        try:
            ts = _parse_iso_ts(m.group("ts"))
        except Exception:
            # fallback: skip unparsable timestamps rather than crash the whole parser
            continue
        msg = m.group("msg")
        events.append((ts, msg))

    if not events:
        return {"totals_seconds": {}, "productive_seconds": 0.0, "idle_seconds": 0.0, "segments": []}

    segments: List[Segment] = []

    # Stateful trackers
    focus_start: Optional[datetime] = None
    slew_block_start: Optional[datetime] = None   # combined Slew+Solve+Center(+Settle)
    wait_start: Optional[Tuple[datetime, str]] = None  # (ts, reason)
    flip_start: Optional[datetime] = None

    # Iterate
    for i, (ts, msg) in enumerate(events):
        # ---- Focus ----
        if PAT["start_autofocus"].search(msg):
            focus_start = ts
            continue
        if PAT["done_autofocus"].search(msg) and focus_start:
            _accumulate(segments, focus_start, ts, "focus")
            focus_start = None
            continue

        # ---- Slew+Solve+Center(+Settle) as a single block ----
        if PAT["start_slew"].search(msg):
            # start/extend block
            if not slew_block_start:
                slew_block_start = ts
            continue
        if PAT["solve_begin"].search(msg):
            if not slew_block_start:
                slew_block_start = ts
            continue
        if PAT["sync"].search(msg):
            # syncing is within the block; ensure block started
            if not slew_block_start:
                slew_block_start = ts
            continue
        if PAT["phd_settle_begin"].search(msg):
            if not slew_block_start:
                slew_block_start = ts
            continue
        if PAT["phd_settle_end"].search(msg):
            if slew_block_start:
                _accumulate(segments, slew_block_start, ts, "slew_solve_center")
                slew_block_start = None
            continue
        if PAT["center_finish"].search(msg):
            if slew_block_start:
                _accumulate(segments, slew_block_start, ts, "slew_solve_center")
                slew_block_start = None
            continue

        # ---- Idle waits (intentional) ----
        if PAT["wait_time_begin"].search(msg):
            wait_start = (ts, "WaitForTime")
            continue
        if PAT["wait_alt_begin"].search(msg):
            wait_start = (ts, "WaitForAltitude")
            continue
        if PAT["wait_safe_begin"].search(msg):
            wait_start = (ts, "WaitUntilSafe")
            continue
        if PAT["wait_generic_end"].search(msg) and wait_start:
            _accumulate(segments, wait_start[0], ts, "idle", reason=wait_start[1])
            wait_start = None
            continue

        # ---- Captures + download gap ----
        mcap = PAT["capture_begin"].search(msg)
        if mcap:
            exp_s = float(mcap.group("exp"))
            exp_end = ts + timedelta(seconds=exp_s)
            # exposure segment
            _accumulate(segments, ts, exp_end, "capture", exp_s=exp_s)

            # next event time to estimate download gap
            next_ts = events[i+1][0] if i + 1 < len(events) else exp_end
            gap_s = (next_ts - exp_end).total_seconds()
            if 0.0 < gap_s <= download_gap_cap_s:
                _accumulate(segments, exp_end, next_ts, "download", gap_s=round(gap_s, 3))
            continue

        # ---- Meridian flip (if it actually occurs) ----
        if PAT["flip_start"].search(msg) and not flip_start:
            flip_start = ts
            continue
        if PAT["flip_done"].search(msg) and flip_start:
            _accumulate(segments, flip_start, ts, "meridian_flip")
            flip_start = None
            continue

    # If any open blocks remain (rare), close them at the last timestamp
    last_ts = events[-1][0]
    if focus_start:
        _accumulate(segments, focus_start, last_ts, "focus")
    if slew_block_start:
        _accumulate(segments, slew_block_start, last_ts, "slew_solve_center")
    if wait_start:
        _accumulate(segments, wait_start[0], last_ts, "idle", reason=wait_start[1])
    if flip_start:
        _accumulate(segments, flip_start, last_ts, "meridian_flip")

    # Merge small gaps for identical labels
    segments = _merge_adjacent(segments, join_window_s=join_window_s)

    # Totals
    totals = defaultdict(float)
    for s in segments:
        totals[s.label] += s.duration_s

    productive_labels = {"capture", "download", "slew_solve_center", "focus"}
    productive_s = sum(v for k, v in totals.items() if k in productive_labels)
    idle_s = sum(v for k, v in totals.items() if k not in productive_labels)

    return {
        "totals_seconds": {k: round(v, 3) for k, v in sorted(totals.items())},
        "productive_seconds": round(productive_s, 3),
        "idle_seconds": round(idle_s, 3),
        "segments": [
            {
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "label": s.label,
                "duration_seconds": round(s.duration_s, 3),
                "meta": s.meta
            } for s in segments
        ]
    }

# ---------------------- FastAPI service ----------------------
try:
    from fastapi import FastAPI, UploadFile, File
    from fastapi.responses import JSONResponse
except Exception:
    FastAPI = None

def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI not installed. pip install fastapi uvicorn")
    app = FastAPI(title="NINA Session Analyzer")

    @app.post("/analyze")
    async def analyze(file: UploadFile = File(...), download_gap_cap_s: float = 20.0):
        text = (await file.read()).decode("utf-8", errors="ignore")
        result = parse_nina_log(text, download_gap_cap_s=download_gap_cap_s)
        return JSONResponse(result)

    return app

if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python nina_session_analyzer.py <NINA.log>", file=sys.stderr)
        sys.exit(1)
    p = sys.argv[1]
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    print(json.dumps(parse_nina_log(text), indent=2))
