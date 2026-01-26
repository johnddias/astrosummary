"""
PHD2 Debug Log Parser

Parses PHD2 debug logs to extract settling statistics, dither commands,
and correlate with imaging session events.

Debug logs contain JSON events for:
- SettleDone: success/failure status, frame count, error messages
- Settling: progress updates with distance and time within threshold
- Dither commands: amount, settle parameters (pixels, time, timeout)
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger("backend.phd2_debug_parser")

# Pattern to extract timestamp and JSON from debug log lines
# Format: HH:MM:SS.mmm XX.XXX THREAD evsrv: {JSON} or evsrv: cli XXXXX request: {JSON}
DEBUG_LINE_RE = re.compile(
    r'^(?P<time>\d{2}:\d{2}:\d{2}\.\d{3})\s+'  # Timestamp
    r'[\d.]+\s+'                                # Delta time
    r'\d+\s+'                                   # Thread ID
    r'evsrv:\s*'                                # Event server marker
    r'(?:cli\s+[A-F0-9]+\s+(?:request|response):\s*)?'  # Optional client info
    r'(?P<json>\{.+\})\s*$'                     # JSON payload
)

# Pattern to extract date from "Guiding Begins at" lines
GUIDING_BEGINS_RE = re.compile(
    r'Guiding Begins at\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})'
)

# Pattern to extract log file date from filename
LOG_FILENAME_RE = re.compile(
    r'PHD2_DebugLog_(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{6})\.txt'
)


@dataclass
class SettleEvent:
    """A single settle completion event from PHD2"""
    timestamp: datetime
    status: int  # 0 = success, 1 = failure
    total_frames: int
    dropped_frames: int = 0
    error: Optional[str] = None
    settle_time_sec: float = 0.0  # Calculated from total_frames

    @property
    def success(self) -> bool:
        return self.status == 0

    @property
    def failure_reason(self) -> Optional[str]:
        if self.status == 0:
            return None
        if self.error:
            if "timed-out" in self.error.lower():
                return "timeout"
            elif "guide star" in self.error.lower():
                return "lost_star"
            elif "stopped" in self.error.lower():
                return "guiding_stopped"
            else:
                return "other"
        return "unknown"


@dataclass
class DitherCommand:
    """A dither command sent to PHD2"""
    timestamp: datetime
    amount: float
    ra_only: bool
    settle_pixels: float
    settle_time: float
    settle_timeout: float
    request_id: Optional[str] = None


@dataclass
class SettleProgress:
    """A settling progress update"""
    timestamp: datetime
    distance: float  # Current distance from lock position in pixels
    time_in_threshold: float  # Seconds within threshold so far
    settle_time_required: float  # Required seconds (usually 10)
    star_locked: bool


@dataclass
class SettleStatistics:
    """Aggregate statistics for settling performance"""
    total_attempts: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: float = 0.0

    # Timing stats (successful settles only)
    avg_settle_time_sec: float = 0.0
    min_settle_time_sec: float = 0.0
    max_settle_time_sec: float = 0.0
    median_settle_time_sec: float = 0.0

    # Frame count distribution
    frame_distribution: Dict[int, int] = field(default_factory=dict)

    # Failure breakdown
    failure_reasons: Dict[str, int] = field(default_factory=dict)

    # Per-session breakdown
    sessions: List[Dict] = field(default_factory=list)


class PHD2DebugParser:
    """Parser for PHD2 debug logs"""

    # Approximate frame time in seconds (2s exposure + overhead)
    FRAME_TIME_SEC = 2.6

    def __init__(self):
        self.settle_events: List[SettleEvent] = []
        self.dither_commands: List[DitherCommand] = []
        self.settle_progress: List[SettleProgress] = []
        self._current_date: Optional[datetime] = None

    def parse_log_directory(self, log_dir: str) -> SettleStatistics:
        """
        Parse all PHD2 debug logs in a directory.

        Args:
            log_dir: Path to directory containing PHD2 debug log files

        Returns:
            Aggregated SettleStatistics from all logs
        """
        log_path = Path(log_dir)
        if not log_path.exists() or not log_path.is_dir():
            logger.error(f"PHD2 debug log directory not found: {log_dir}")
            return SettleStatistics()

        log_files = sorted(log_path.glob("PHD2_DebugLog_*.txt"))

        if not log_files:
            logger.warning(f"No PHD2 debug log files found in {log_dir}")
            return SettleStatistics()

        logger.info(f"Found {len(log_files)} PHD2 debug log files in {log_dir}")

        all_settle_events: List[SettleEvent] = []
        all_dither_commands: List[DitherCommand] = []
        session_stats: List[Dict] = []

        for log_file in log_files:
            try:
                events, dithers = self.parse_log(str(log_file))
                all_settle_events.extend(events)
                all_dither_commands.extend(dithers)

                # Calculate per-session stats
                if events:
                    successful = sum(1 for e in events if e.success)
                    session_stats.append({
                        "file": log_file.name,
                        "date": log_file.name[15:25],  # Extract date from filename
                        "total": len(events),
                        "successful": successful,
                        "failed": len(events) - successful,
                        "success_rate": round(successful / len(events) * 100, 1) if events else 0
                    })
                    logger.info(f"Loaded {len(events)} settle events from {log_file.name}")
            except Exception as e:
                logger.warning(f"Failed to parse {log_file.name}: {e}")
                continue

        # Compute aggregate statistics
        stats = self._compute_statistics(all_settle_events)
        stats.sessions = session_stats

        self.settle_events = all_settle_events
        self.dither_commands = all_dither_commands

        return stats

    def parse_log(self, log_path: str) -> Tuple[List[SettleEvent], List[DitherCommand]]:
        """
        Parse a single PHD2 debug log file.

        Args:
            log_path: Path to PHD2 debug log file

        Returns:
            Tuple of (settle_events, dither_commands)
        """
        log_file = Path(log_path)
        if not log_file.exists():
            logger.error(f"PHD2 debug log not found: {log_path}")
            return [], []

        settle_events: List[SettleEvent] = []
        dither_commands: List[DitherCommand] = []

        # Try to extract date from filename
        filename_match = LOG_FILENAME_RE.match(log_file.name)
        if filename_match:
            date_str = filename_match.group("date")
            self._current_date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            self._current_date = None

        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Check for "Guiding Begins" to update date context
                    guiding_match = GUIDING_BEGINS_RE.search(line)
                    if guiding_match:
                        date_str = guiding_match.group("date")
                        self._current_date = datetime.strptime(date_str, "%Y-%m-%d")
                        continue

                    # Try to parse JSON event line
                    debug_match = DEBUG_LINE_RE.match(line)
                    if not debug_match:
                        continue

                    time_str = debug_match.group("time")
                    json_str = debug_match.group("json")

                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        continue

                    # Handle different event types
                    if "Event" in data:
                        event_type = data.get("Event")

                        # Parse timestamp (pass json_data to use Unix timestamp if available)
                        timestamp = self._parse_timestamp(time_str, data)
                        if not timestamp:
                            continue

                        if event_type == "SettleDone":
                            settle_event = self._parse_settle_done(timestamp, data)
                            if settle_event:
                                settle_events.append(settle_event)

                        elif event_type == "Settling":
                            progress = self._parse_settling_progress(timestamp, data)
                            if progress:
                                self.settle_progress.append(progress)

                    elif "method" in data:
                        method = data.get("method")

                        # Parse timestamp for dither commands (no Unix timestamp, use time string)
                        timestamp = self._parse_timestamp(time_str, data)
                        if not timestamp:
                            continue

                        if method == "dither":
                            dither = self._parse_dither_command(timestamp, data)
                            if dither:
                                dither_commands.append(dither)

            return settle_events, dither_commands

        except Exception as e:
            logger.error(f"Error parsing PHD2 debug log {log_path}: {e}")
            return [], []

    def _parse_timestamp(self, time_str: str, json_data: dict = None) -> Optional[datetime]:
        """Parse time string and combine with current date.

        If json_data contains a Unix 'Timestamp' field, use that directly.
        Otherwise fall back to combining time_str with current date.
        """
        # Prefer Unix timestamp from JSON if available
        if json_data and "Timestamp" in json_data:
            try:
                unix_ts = json_data["Timestamp"]
                timestamp = datetime.fromtimestamp(unix_ts)
                # Update current date from Unix timestamp for events without it
                self._current_date = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                return timestamp
            except (ValueError, OSError, TypeError):
                pass

        # Fall back to time string + current date
        if not self._current_date:
            return None

        try:
            time_parts = datetime.strptime(time_str, "%H:%M:%S.%f")
            timestamp = self._current_date.replace(
                hour=time_parts.hour,
                minute=time_parts.minute,
                second=time_parts.second,
                microsecond=time_parts.microsecond
            )

            # Handle day rollover (times after midnight)
            if hasattr(self, '_last_timestamp') and self._last_timestamp:
                if timestamp < self._last_timestamp - timedelta(hours=12):
                    timestamp += timedelta(days=1)
                    self._current_date += timedelta(days=1)

            self._last_timestamp = timestamp
            return timestamp

        except ValueError:
            return None

    def _parse_settle_done(self, timestamp: datetime, data: dict) -> Optional[SettleEvent]:
        """Parse a SettleDone event."""
        try:
            status = data.get("Status", 0)
            total_frames = data.get("TotalFrames", 0)
            dropped_frames = data.get("DroppedFrames", 0)
            error = data.get("Error")

            # Calculate approximate settle time from frame count
            settle_time_sec = total_frames * self.FRAME_TIME_SEC

            return SettleEvent(
                timestamp=timestamp,
                status=status,
                total_frames=total_frames,
                dropped_frames=dropped_frames,
                error=error,
                settle_time_sec=settle_time_sec
            )
        except Exception as e:
            logger.debug(f"Failed to parse SettleDone: {e}")
            return None

    def _parse_settling_progress(self, timestamp: datetime, data: dict) -> Optional[SettleProgress]:
        """Parse a Settling progress event."""
        try:
            return SettleProgress(
                timestamp=timestamp,
                distance=data.get("Distance", 0.0),
                time_in_threshold=data.get("Time", 0.0),
                settle_time_required=data.get("SettleTime", 10.0),
                star_locked=data.get("StarLocked", False)
            )
        except Exception as e:
            logger.debug(f"Failed to parse Settling: {e}")
            return None

    def _parse_dither_command(self, timestamp: datetime, data: dict) -> Optional[DitherCommand]:
        """Parse a dither command."""
        try:
            params = data.get("params", {})
            settle = params.get("settle", {})

            return DitherCommand(
                timestamp=timestamp,
                amount=params.get("amount", 0.0),
                ra_only=params.get("raOnly", False),
                settle_pixels=settle.get("pixels", 1.5),
                settle_time=settle.get("time", 10.0),
                settle_timeout=settle.get("timeout", 60.0),
                request_id=data.get("id")
            )
        except Exception as e:
            logger.debug(f"Failed to parse dither command: {e}")
            return None

    def _compute_statistics(self, events: List[SettleEvent]) -> SettleStatistics:
        """Compute aggregate statistics from settle events."""
        if not events:
            return SettleStatistics()

        successful_events = [e for e in events if e.success]
        failed_events = [e for e in events if not e.success]

        # Basic counts
        total = len(events)
        successful = len(successful_events)
        failed = len(failed_events)
        success_rate = successful / total * 100 if total > 0 else 0.0

        # Timing statistics (successful only)
        settle_times = [e.settle_time_sec for e in successful_events]
        if settle_times:
            avg_time = sum(settle_times) / len(settle_times)
            min_time = min(settle_times)
            max_time = max(settle_times)
            sorted_times = sorted(settle_times)
            median_time = sorted_times[len(sorted_times) // 2]
        else:
            avg_time = min_time = max_time = median_time = 0.0

        # Frame distribution
        frame_dist: Dict[int, int] = defaultdict(int)
        for e in successful_events:
            frame_dist[e.total_frames] += 1

        # Failure reasons
        failure_reasons: Dict[str, int] = defaultdict(int)
        for e in failed_events:
            reason = e.failure_reason or "unknown"
            failure_reasons[reason] += 1

        return SettleStatistics(
            total_attempts=total,
            successful=successful,
            failed=failed,
            success_rate=round(success_rate, 1),
            avg_settle_time_sec=round(avg_time, 1),
            min_settle_time_sec=round(min_time, 1),
            max_settle_time_sec=round(max_time, 1),
            median_settle_time_sec=round(median_time, 1),
            frame_distribution=dict(sorted(frame_dist.items())),
            failure_reasons=dict(failure_reasons)
        )

    def get_settle_events_as_dicts(self) -> List[Dict]:
        """Return settle events as list of dictionaries for JSON serialization."""
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "success": e.success,
                "status": e.status,
                "total_frames": e.total_frames,
                "dropped_frames": e.dropped_frames,
                "settle_time_sec": round(e.settle_time_sec, 1),
                "error": e.error,
                "failure_reason": e.failure_reason
            }
            for e in self.settle_events
        ]

    def get_dither_commands_as_dicts(self) -> List[Dict]:
        """Return dither commands as list of dictionaries for JSON serialization."""
        return [
            {
                "timestamp": d.timestamp.isoformat(),
                "amount": d.amount,
                "ra_only": d.ra_only,
                "settle_pixels": d.settle_pixels,
                "settle_time": d.settle_time,
                "settle_timeout": d.settle_timeout
            }
            for d in self.dither_commands
        ]

    def correlate_with_nina_dithers(
        self,
        nina_dither_timestamps: List[datetime],
        tolerance_seconds: float = 10.0
    ) -> List[Dict]:
        """
        Correlate PHD2 settle events with NINA dither commands.

        Args:
            nina_dither_timestamps: List of dither start times from NINA log
            tolerance_seconds: Maximum time difference for correlation

        Returns:
            List of correlated events with both NINA and PHD2 data
        """
        correlations = []

        for nina_ts in nina_dither_timestamps:
            # Find matching PHD2 settle event
            best_match = None
            best_delta = float('inf')

            for settle in self.settle_events:
                delta = abs((settle.timestamp - nina_ts).total_seconds())
                if delta < best_delta and delta < tolerance_seconds + 60:  # Allow for settle time
                    best_delta = delta
                    best_match = settle

            correlations.append({
                "nina_dither_time": nina_ts.isoformat(),
                "phd2_settle": {
                    "timestamp": best_match.timestamp.isoformat() if best_match else None,
                    "success": best_match.success if best_match else None,
                    "settle_time_sec": best_match.settle_time_sec if best_match else None,
                    "error": best_match.error if best_match else None
                } if best_match else None,
                "time_delta_sec": round(best_delta, 1) if best_match else None
            })

        return correlations


def parse_phd2_debug_log(log_path: str) -> Dict:
    """
    Convenience function to parse a single PHD2 debug log.

    Returns:
        Dictionary with settle statistics and event details
    """
    parser = PHD2DebugParser()
    events, dithers = parser.parse_log(log_path)

    if not events:
        return {
            "success": False,
            "error": "No settle events found in log",
            "statistics": None,
            "sessions": [],
            "events": [],
            "dithers": []
        }

    stats = parser._compute_statistics(events)
    parser.settle_events = events
    parser.dither_commands = dithers

    return {
        "success": True,
        "statistics": {
            "total_attempts": stats.total_attempts,
            "successful": stats.successful,
            "failed": stats.failed,
            "success_rate": stats.success_rate,
            "avg_settle_time_sec": stats.avg_settle_time_sec,
            "min_settle_time_sec": stats.min_settle_time_sec,
            "max_settle_time_sec": stats.max_settle_time_sec,
            "median_settle_time_sec": stats.median_settle_time_sec,
            "frame_distribution": stats.frame_distribution,
            "failure_reasons": stats.failure_reasons
        },
        "sessions": [],  # Single file has no per-session breakdown
        "events": parser.get_settle_events_as_dicts(),
        "dithers": parser.get_dither_commands_as_dicts()
    }


def parse_phd2_debug_directory(log_dir: str) -> Dict:
    """
    Convenience function to parse all PHD2 debug logs in a directory.

    Returns:
        Dictionary with aggregate statistics and per-session breakdown
    """
    parser = PHD2DebugParser()
    stats = parser.parse_log_directory(log_dir)

    return {
        "success": True,
        "statistics": {
            "total_attempts": stats.total_attempts,
            "successful": stats.successful,
            "failed": stats.failed,
            "success_rate": stats.success_rate,
            "avg_settle_time_sec": stats.avg_settle_time_sec,
            "min_settle_time_sec": stats.min_settle_time_sec,
            "max_settle_time_sec": stats.max_settle_time_sec,
            "median_settle_time_sec": stats.median_settle_time_sec,
            "frame_distribution": stats.frame_distribution,
            "failure_reasons": stats.failure_reasons
        },
        "sessions": stats.sessions,
        "events": parser.get_settle_events_as_dicts(),
        "dithers": parser.get_dither_commands_as_dicts()
    }
