from __future__ import annotations
import re
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, asdict, field
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
    "roof_closing": re.compile(r'\bRoof closing\b'),
    "roof_opening": re.compile(r'\bRoof opening\b'),
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
    # RMS threshold warnings from guiding
    "rms_above_threshold": re.compile(r'(?P<axis>Total|RA|Dec) RMS above threshold \((?P<rms>[0-9.]+)\s*/\s*(?P<threshold>[0-9.]+)\)'),
    # Dither events for correlation
    "dither_start": re.compile(r'\bStarting Category:\s*Guider,\s*Item:\s*Dither\b'),
    "dither_end": re.compile(r'\bFinishing Category:\s*Guider,\s*Item:\s*Dither\b'),
    # Filter change for correlation
    "filter_change": re.compile(r'\bSwitching Filter to\b'),
    # Settings changes - capture RMS threshold and settle parameters
    "settle_pixel_setting": re.compile(r'(?:Settle\s*(?:Pixel\s*)?(?:Tolerance|Threshold)|SettlePixels)\s*[=:]\s*(?P<value>[0-9.]+)', re.IGNORECASE),
    "settle_time_setting": re.compile(r'(?:Settle\s*(?:Time(?:out)?|Duration)|SettleTime|MinimumSettleTime)\s*[=:]\s*(?P<value>[0-9.]+)', re.IGNORECASE),
    "rms_threshold_setting": re.compile(r'(?:RMS\s*Threshold|GuideRMSThreshold)\s*[=:]\s*(?P<value>[0-9.]+)', re.IGNORECASE),
    # PHD2 connected/settings loaded
    "phd2_connected": re.compile(r'PHD2.*(?:connected|Connected)', re.IGNORECASE),
    # Dither amount/pixels setting
    "dither_pixels_setting": re.compile(r'(?:Dither\s*(?:Pixels|Amount|Scale))\s*[=:]\s*(?P<value>[0-9.]+)', re.IGNORECASE),
    # InterruptWhenRMSAbove settings line: "InterruptWhenRMSAbove, Mode RMS, Threshold 1.1, Points 7"
    "interrupt_rms_settings": re.compile(r'InterruptWhenRMSAbove.*Threshold\s+(?P<threshold>[0-9.]+).*Points\s+(?P<points>\d+)', re.IGNORECASE),
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


@dataclass
class RmsThresholdEvent:
    """Single RMS above threshold event from NINA log"""
    timestamp: datetime
    axis: str  # "total", "ra", or "dec"
    rms: float
    threshold: float
    line: str = ""


@dataclass
class RmsBurst:
    """Group of consecutive RMS threshold events"""
    start_ts: datetime
    end_ts: datetime
    events: List[RmsThresholdEvent] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @property
    def duration_sec(self) -> float:
        return max(0.0, (self.end_ts - self.start_ts).total_seconds())

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def peak_rms(self) -> float:
        return max((e.rms for e in self.events), default=0.0)

    @property
    def avg_rms(self) -> float:
        if not self.events:
            return 0.0
        return sum(e.rms for e in self.events) / len(self.events)

    @property
    def axes(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"total": 0, "ra": 0, "dec": 0}
        for e in self.events:
            axis_key = e.axis.lower()
            if axis_key in counts:
                counts[axis_key] += 1
        return counts


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


def _group_rms_into_bursts(
    rms_events: List[RmsThresholdEvent],
    burst_gap_seconds: float = 2.5
) -> List[RmsBurst]:
    """Group consecutive RMS threshold events into bursts.

    Events within burst_gap_seconds of each other are grouped together.
    """
    if not rms_events:
        return []

    sorted_events = sorted(rms_events, key=lambda e: e.timestamp)
    bursts: List[RmsBurst] = []

    current_burst = RmsBurst(
        start_ts=sorted_events[0].timestamp,
        end_ts=sorted_events[0].timestamp,
        events=[sorted_events[0]]
    )

    for event in sorted_events[1:]:
        gap = (event.timestamp - current_burst.end_ts).total_seconds()
        if gap <= burst_gap_seconds:
            # Continue current burst
            current_burst.events.append(event)
            current_burst.end_ts = event.timestamp
        else:
            # Start new burst
            bursts.append(current_burst)
            current_burst = RmsBurst(
                start_ts=event.timestamp,
                end_ts=event.timestamp,
                events=[event]
            )

    # Don't forget the last burst
    bursts.append(current_burst)
    return bursts


@dataclass
class CorrelationEvent:
    """An event that can be correlated with RMS bursts"""
    timestamp: datetime
    event_type: str  # "dither", "autofocus", "filter_change", "slew", "flip"


@dataclass
class SettingsChange:
    """A settings change detected in the log"""
    timestamp: datetime
    setting_type: str  # "settle_pixels", "settle_time", "rms_threshold", "dither_pixels"
    value: float
    raw_line: str = ""
    note: str = ""


def _correlate_bursts_with_events(
    bursts: List[RmsBurst],
    correlation_events: List[CorrelationEvent],
    window_seconds: float = 60.0
) -> None:
    """Tag bursts with nearby session events (in-place mutation)."""
    if not bursts or not correlation_events:
        return

    sorted_events = sorted(correlation_events, key=lambda e: e.timestamp)

    for burst in bursts:
        burst_start = burst.start_ts
        window_start = burst_start - timedelta(seconds=window_seconds)
        window_end = burst_start + timedelta(seconds=window_seconds)

        for ce in sorted_events:
            if ce.timestamp < window_start:
                continue
            if ce.timestamp > window_end:
                break
            tag = f"near_{ce.event_type}"
            if tag not in burst.tags:
                burst.tags.append(tag)


def _compute_hourly_rollups(
    rms_events: List[RmsThresholdEvent],
    bursts: List[RmsBurst]
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Compute events and bursts per hour."""
    events_per_hour: Dict[str, int] = defaultdict(int)
    bursts_per_hour: Dict[str, int] = defaultdict(int)

    for event in rms_events:
        hour_key = event.timestamp.strftime("%Y-%m-%d %H:00")
        events_per_hour[hour_key] += 1

    for burst in bursts:
        hour_key = burst.start_ts.strftime("%Y-%m-%d %H:00")
        bursts_per_hour[hour_key] += 1

    return dict(events_per_hour), dict(bursts_per_hour)


def _detect_threshold_changes(rms_events: List[RmsThresholdEvent]) -> List[Dict[str, object]]:
    """Detect when the RMS threshold setting changed based on values in warning messages."""
    if not rms_events:
        return []

    sorted_events = sorted(rms_events, key=lambda e: e.timestamp)
    changes: List[Dict[str, object]] = []
    last_threshold: Optional[float] = None

    for event in sorted_events:
        if last_threshold is None:
            # First threshold seen - record as initial setting
            changes.append({
                "ts": event.timestamp.isoformat(),
                "setting_type": "rms_threshold",
                "value": round(event.threshold, 4),
                "note": "initial"
            })
            last_threshold = event.threshold
        elif abs(event.threshold - last_threshold) > 0.001:
            # Threshold changed
            changes.append({
                "ts": event.timestamp.isoformat(),
                "setting_type": "rms_threshold",
                "value": round(event.threshold, 4),
                "note": f"changed from {round(last_threshold, 4)}"
            })
            last_threshold = event.threshold

    return changes


def _compute_rms_analysis(
    rms_events: List[RmsThresholdEvent],
    correlation_events: List[CorrelationEvent],
    settings_changes: List[SettingsChange] = None,
    burst_gap_seconds: float = 2.5,
    correlation_window_seconds: float = 60.0
) -> Dict[str, object]:
    """Compute full RMS threshold analysis."""
    if settings_changes is None:
        settings_changes = []

    # Detect threshold changes from RMS events themselves
    threshold_changes = _detect_threshold_changes(rms_events)

    # Combine explicit settings changes with detected threshold changes
    settings_output = [
        {
            "ts": sc.timestamp.isoformat(),
            "setting_type": sc.setting_type,
            "value": sc.value,
            "note": sc.note,
        }
        for sc in sorted(settings_changes, key=lambda x: x.timestamp)
    ]
    settings_output.extend(threshold_changes)
    # Sort combined list by timestamp
    settings_output = sorted(settings_output, key=lambda x: x["ts"])

    if not rms_events:
        return {
            "total_event_count": 0,
            "total_burst_count": 0,
            "worst_hour_by_events": None,
            "worst_hour_by_bursts": None,
            "max_peak_rms": None,
            "bursts": [],
            "events": [],
            "events_per_hour": {},
            "bursts_per_hour": {},
            "correlation": {
                "burst_window_sec": correlation_window_seconds,
                "percent_bursts_near_dither": 0.0,
                "percent_bursts_near_autofocus": 0.0,
            },
            "settings_changes": settings_output,
        }

    # Group into bursts
    bursts = _group_rms_into_bursts(rms_events, burst_gap_seconds)

    # Correlate with events
    _correlate_bursts_with_events(bursts, correlation_events, correlation_window_seconds)

    # Hourly rollups
    events_per_hour, bursts_per_hour = _compute_hourly_rollups(rms_events, bursts)

    # Find worst hours
    worst_hour_by_events = max(events_per_hour.items(), key=lambda x: x[1])[0] if events_per_hour else None
    worst_hour_by_bursts = max(bursts_per_hour.items(), key=lambda x: x[1])[0] if bursts_per_hour else None

    # Max peak RMS
    max_peak_rms = max((b.peak_rms for b in bursts), default=None)

    # Correlation percentages
    bursts_near_dither = sum(1 for b in bursts if "near_dither" in b.tags)
    bursts_near_autofocus = sum(1 for b in bursts if "near_autofocus" in b.tags)
    total_bursts = len(bursts)

    percent_near_dither = (bursts_near_dither / total_bursts * 100) if total_bursts > 0 else 0.0
    percent_near_autofocus = (bursts_near_autofocus / total_bursts * 100) if total_bursts > 0 else 0.0

    return {
        "total_event_count": len(rms_events),
        "total_burst_count": len(bursts),
        "worst_hour_by_events": worst_hour_by_events,
        "worst_hour_by_bursts": worst_hour_by_bursts,
        "max_peak_rms": round(max_peak_rms, 4) if max_peak_rms else None,
        "bursts": [
            {
                "start_ts": b.start_ts.isoformat(),
                "end_ts": b.end_ts.isoformat(),
                "duration_sec": round(b.duration_sec, 2),
                "event_count": b.event_count,
                "peak_rms": round(b.peak_rms, 4),
                "avg_rms": round(b.avg_rms, 4),
                "axes": b.axes,
                "tags": b.tags,
            }
            for b in bursts
        ],
        "events": [
            {
                "ts": e.timestamp.isoformat(),
                "axis": e.axis.lower(),
                "rms": round(e.rms, 4),
                "threshold": round(e.threshold, 4),
            }
            for e in rms_events
        ],
        "events_per_hour": events_per_hour,
        "bursts_per_hour": bursts_per_hour,
        "correlation": {
            "burst_window_sec": correlation_window_seconds,
            "percent_bursts_near_dither": round(percent_near_dither, 1),
            "percent_bursts_near_autofocus": round(percent_near_autofocus, 1),
        },
        "settings_changes": settings_output,
    }


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
            "rms_analysis": _compute_rms_analysis([], []),
        }

    segments: List[Segment] = []
    rms_events: List[RmsThresholdEvent] = []
    correlation_events: List[CorrelationEvent] = []
    settings_changes: List[SettingsChange] = []

    # Track last seen settings values to only log changes
    last_settings: Dict[str, float] = {}

    focus_start: Optional[datetime] = None
    slew_block_start: Optional[datetime] = None
    wait_start: Optional[Tuple[datetime, str]] = None
    flip_start: Optional[datetime] = None
    roof_closed_start: Optional[datetime] = None

    for i, (ts, msg) in enumerate(events):
        # Collect RMS threshold events
        rms_match = PAT["rms_above_threshold"].search(msg)
        if rms_match:
            rms_events.append(RmsThresholdEvent(
                timestamp=ts,
                axis=rms_match.group("axis").lower(),
                rms=float(rms_match.group("rms")),
                threshold=float(rms_match.group("threshold")),
                line=msg
            ))

        # Collect correlation events (dither, filter change)
        if PAT["dither_start"].search(msg):
            correlation_events.append(CorrelationEvent(ts, "dither"))
        if PAT["filter_change"].search(msg):
            correlation_events.append(CorrelationEvent(ts, "filter_change"))

        # Collect settings changes - only log when values actually CHANGE
        settle_pixel_match = PAT["settle_pixel_setting"].search(msg)
        if settle_pixel_match:
            val = float(settle_pixel_match.group("value"))
            prev = last_settings.get("settle_pixels")
            if prev != val:
                note = "initial" if prev is None else f"changed from {prev}"
                settings_changes.append(SettingsChange(
                    timestamp=ts, setting_type="settle_pixels",
                    value=val, raw_line=msg, note=note
                ))
                last_settings["settle_pixels"] = val

        settle_time_match = PAT["settle_time_setting"].search(msg)
        if settle_time_match:
            val = float(settle_time_match.group("value"))
            prev = last_settings.get("settle_time")
            if prev != val:
                note = "initial" if prev is None else f"changed from {prev}"
                settings_changes.append(SettingsChange(
                    timestamp=ts, setting_type="settle_time",
                    value=val, raw_line=msg, note=note
                ))
                last_settings["settle_time"] = val

        rms_thresh_match = PAT["rms_threshold_setting"].search(msg)
        if rms_thresh_match:
            val = float(rms_thresh_match.group("value"))
            prev = last_settings.get("rms_threshold")
            if prev != val:
                note = "initial" if prev is None else f"changed from {prev}"
                settings_changes.append(SettingsChange(
                    timestamp=ts, setting_type="rms_threshold",
                    value=val, raw_line=msg, note=note
                ))
                last_settings["rms_threshold"] = val

        dither_px_match = PAT["dither_pixels_setting"].search(msg)
        if dither_px_match:
            val = float(dither_px_match.group("value"))
            prev = last_settings.get("dither_pixels")
            if prev != val:
                note = "initial" if prev is None else f"changed from {prev}"
                settings_changes.append(SettingsChange(
                    timestamp=ts, setting_type="dither_pixels",
                    value=val, raw_line=msg, note=note
                ))
                last_settings["dither_pixels"] = val
        # InterruptWhenRMSAbove settings line (captures both threshold and points)
        # Only log when values actually CHANGE
        interrupt_match = PAT["interrupt_rms_settings"].search(msg)
        if interrupt_match:
            threshold_val = float(interrupt_match.group("threshold"))
            points_val = float(interrupt_match.group("points"))

            # Only record threshold if it changed
            prev_thresh = last_settings.get("rms_threshold_config")
            if prev_thresh != threshold_val:
                note = "initial" if prev_thresh is None else f"changed from {prev_thresh}"
                settings_changes.append(SettingsChange(
                    timestamp=ts, setting_type="rms_threshold_config",
                    value=threshold_val, raw_line=msg, note=note
                ))
                last_settings["rms_threshold_config"] = threshold_val

            # Only record points if it changed
            prev_pts = last_settings.get("rms_points")
            if prev_pts != points_val:
                note = "initial" if prev_pts is None else f"changed from {int(prev_pts)}"
                settings_changes.append(SettingsChange(
                    timestamp=ts, setting_type="rms_points",
                    value=points_val, raw_line=msg, note=note
                ))
                last_settings["rms_points"] = points_val

        if PAT["start_autofocus"].search(msg):
            focus_start = ts
            correlation_events.append(CorrelationEvent(ts, "autofocus"))
            continue
        if PAT["done_autofocus"].search(msg) and focus_start:
            _accumulate(segments, focus_start, ts, "focus")
            focus_start = None
            continue

        if PAT["center_start"].search(msg):
            slew_block_start = ts
            correlation_events.append(CorrelationEvent(ts, "slew"))
            continue
        if PAT["center_finish"].search(msg):
            if slew_block_start:
                _accumulate(segments, slew_block_start, ts, "slew_solve_center")
                slew_block_start = None
            continue

        if PAT["roof_closing"].search(msg):
            roof_closed_start = ts
            continue
        if PAT["roof_opening"].search(msg):
            if roof_closed_start:
                _accumulate(segments, roof_closed_start, ts, "idle", reason="WaitingForRoof")
                roof_closed_start = None
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
                correlation_events.append(CorrelationEvent(ts, "flip"))
            else:
                # advance to the later physical start if this is after the existing start
                if ts > flip_start:
                    flip_start = ts
            continue
        # Fallback to generic flip_start if we haven't seen a physical start
        if PAT["flip_start"].search(msg) and not flip_start:
            flip_start = ts
            correlation_events.append(CorrelationEvent(ts, "flip"))
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
    if roof_closed_start:
        _accumulate(segments, roof_closed_start, last_ts, "idle", reason="WaitingForRoof")

    segments = _merge_adjacent(segments, join_window_s=join_window_s)

    totals = defaultdict(float)
    for s in segments:
        totals[s.label] += s.duration_s

    productive_labels = {"capture", "download", "slew_solve_center", "focus"}
    productive_s = sum(v for k, v in totals.items() if k in productive_labels)
    idle_s = sum(v for k, v in totals.items() if k not in productive_labels)

    # Compute RMS analysis
    rms_analysis = _compute_rms_analysis(rms_events, correlation_events, settings_changes)

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
        "rms_analysis": rms_analysis,
    }
