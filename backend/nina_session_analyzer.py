from __future__ import annotations
import re
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Iterable

# Timestamp + message capture
TS_RE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)\|[A-Z]+\|[^|]*\|[^|]*\|\d+\|(?P<msg>.*)$'
)


def _parse_iso_ts(s: str) -> datetime:
    """Parse ISO timestamp strings that may have non-standard fractional second widths.

    Normalize fractional seconds to 6 digits (microseconds) before parsing.
    """
    if '.' not in s:
        return datetime.fromisoformat(s)
    datepart, frac = s.split('.', 1)
    frac = re.sub(r'[^0-9].*$', '', frac)
    if len(frac) > 6:
        frac = frac[:6]
    else:
        frac = frac.ljust(6, '0')
    normalized = f"{datepart}.{frac}"
    return datetime.fromisoformat(normalized)


# Key patterns (keeping minimal set needed for analysis)
PAT = {
    "start_autofocus": re.compile(r'\bStarting Category:\s*Focuser,\s*Item:\s*RunAutofocus\b'),
    "done_autofocus": re.compile(r'\bAutoFocus completed\b'),
    "center_start": re.compile(r'\bStarting Category:\s*Telescope,\s*Item:\s*Center\b'),
    "center_finish": re.compile(r'\bFinishing Category:\s*Telescope,\s*Item:\s*Center\b'),
    "wait_time_begin": re.compile(r'\bStarting Category:\s*Utility,\s*Item:\s*WaitForTime\b'),
    "wait_alt_begin": re.compile(r'\bStarting Category:\s*Utility,\s*Item:\s*WaitForAltitude\b'),
    "wait_safe_begin": re.compile(r'\bStarting Category:\s*Safety Monitor,\s*Item:\s*WaitUntilSafe\b'),
    "wait_generic_end": re.compile(r'\bFinishing Category:\s*(Utility|Safety Monitor),'),
    "capture_begin": re.compile(r'\bStarting Exposure - Exposure Time:\s*(?P<exp>[0-9]+(?:\.[0-9]+)?)s\b'),
    # Accept a few common variants for meridian flip messages seen in NINA logs
    # Only treat explicit initialization/DoMeridianFlip/Starting messages as flip starts.
    # Avoid matching generic "There is still time remaining" lines.
    "flip_start": re.compile(r'(?i)(?:Meridian Flip.*(?:Initializing Meridian Flip|Starting Meridian Flip|DoMeridianFlip|DoFlip|Starting Trigger: MeridianFlipTrigger)|Initializing Meridian Flip)'),
    # Physical/active flip start (slew) — prefer this as the true start when present
    # Match plain 'Slewing to coordinates' which appears in the message payload
    "flip_physical_start": re.compile(r'(?i)(?:Slewing to coordinates|AscomTelescope\.cs\|MeridianFlip.*Slewing to coordinates|Meridian Flip - Scope will flip to coordinates|MeridianFlipVM\.cs\|DoFlip)'),
    # Several messages indicate the flip sequence has completed (recenter/resume guider usually earlier than an "Exiting" log)
    "flip_done_alt": re.compile(r'(?i)(?:Meridian Flip.*Recenter after meridian flip|Meridian Flip.*Resuming Autoguider|ResumeAutoguider|Resuming Autoguider)'),
    "flip_done": re.compile(r'(?i)(?:Meridian Flip.*(?:completed|finished|Exiting meridian flip)|Exiting meridian flip)'),
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
        else:
            merged.append(seg)
    return merged


def parse_nina_log(
    text: str,
    download_gap_cap_s: float = 20.0,
    join_window_s: float = 2.0
) -> Dict[str, object]:
    """Parse a NINA log and produce a categorized session model.

    Adds parsing diagnostics: lines_total, lines_matched, lines_skipped_ts
    """
    lines_total = 0
    lines_matched = 0
    lines_skipped_ts = 0

    events: List[Tuple[datetime, str]] = []
    for ln in text.splitlines():
        lines_total += 1
        m = TS_RE.match(ln)
        if not m:
            continue
        lines_matched += 1
        ts_raw = m.group("ts")
        try:
            ts = _parse_iso_ts(ts_raw)
        except Exception:
            lines_skipped_ts += 1
            continue
        msg = m.group("msg")
        events.append((ts, msg))

    if not events:
        return {
            "totals_seconds": {},
            "productive_seconds": 0.0,
            "idle_seconds": 0.0,
            "segments": [],
            "lines_total": lines_total,
            "lines_matched": lines_matched,
            "lines_skipped_ts": lines_skipped_ts,
        }

    segments: List[Segment] = []

    focus_start: Optional[datetime] = None
    slew_block_start: Optional[datetime] = None
    wait_start: Optional[Tuple[datetime, str]] = None
    flip_start: Optional[datetime] = None

    for i, (ts, msg) in enumerate(events):
        if PAT["start_autofocus"].search(msg):
            focus_start = ts
            continue
        if PAT["done_autofocus"].search(msg) and focus_start:
            _accumulate(segments, focus_start, ts, "focus")
            focus_start = None
            continue

        if PAT["center_start"].search(msg):
            slew_block_start = ts
            continue
        if PAT["center_finish"].search(msg):
            if slew_block_start:
                _accumulate(segments, slew_block_start, ts, "slew_solve_center")
                slew_block_start = None
            continue

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

        mcap = PAT["capture_begin"].search(msg)
        if mcap:
            exp_s = float(mcap.group("exp"))
            exp_end = ts + timedelta(seconds=exp_s)
            _accumulate(segments, ts, exp_end, "capture", exp_s=exp_s)
            next_ts = events[i+1][0] if i + 1 < len(events) else exp_end
            gap_s = (next_ts - exp_end).total_seconds()
            if 0.0 < gap_s <= download_gap_cap_s:
                _accumulate(segments, exp_end, next_ts, "download", gap_s=round(gap_s, 3))
            continue

        # Flip start: prefer a physical slew/start message when available
        if PAT["flip_physical_start"].search(msg):
            # physical slew indicates the scope is actively flipping.
            # If we already saw a generic "Initializing" start earlier, prefer the
            # physical slew timestamp (advance the start) because it reflects when
            # the scope actually began moving.
            if not flip_start:
                flip_start = ts
            else:
                # advance to the later physical start if this is after the existing start
                if ts > flip_start:
                    flip_start = ts
            continue
        # Fallback to generic flip_start if we haven't seen a physical start
        if PAT["flip_start"].search(msg) and not flip_start:
            flip_start = ts
            continue

        # Prefer an earlier "done" marker (recenter/resume guider) if present
        if PAT.get("flip_done_alt") and PAT["flip_done_alt"].search(msg) and flip_start:
            _accumulate(segments, flip_start, ts, "meridian_flip")
            flip_start = None
            continue
        if PAT["flip_done"].search(msg) and flip_start:
            _accumulate(segments, flip_start, ts, "meridian_flip")
            flip_start = None
            continue

    last_ts = events[-1][0]
    if focus_start:
        _accumulate(segments, focus_start, last_ts, "focus")
    if slew_block_start:
        _accumulate(segments, slew_block_start, last_ts, "slew_solve_center")
    if wait_start:
        _accumulate(segments, wait_start[0], last_ts, "idle", reason=wait_start[1])
    if flip_start:
        _accumulate(segments, flip_start, last_ts, "meridian_flip")

    segments = _merge_adjacent(segments, join_window_s=join_window_s)

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
        ],
        "lines_total": lines_total,
        "lines_matched": lines_matched,
        "lines_skipped_ts": lines_skipped_ts,
    }
