"""
Unified Session Analyzer

Combines data from NINA logs, PHD2 logs, and Session Metadata Plugin
to provide comprehensive session analysis with cross-source correlation.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import statistics
import logging

from models import (
    AcquisitionDetails,
    ImageMetaDataRecord,
    WeatherDataRecord,
    CorrelatedFrame,
    SessionSummary,
    UnifiedSessionAnalyzeResponse,
    PHD2SettleStatistics,
    PHD2SettleEvent,
    SessionMetadataResponse,
)
from session_metadata_parser import (
    parse_session_metadata_directory,
    parse_session_metadata_from_content,
)
from nina_session_analyzer import parse_nina_log
from phd2_debug_parser import (
    parse_phd2_debug_log,
    parse_phd2_debug_directory,
    PHD2DebugParser,
)

logger = logging.getLogger("backend.unified_session_analyzer")


def _parse_iso_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime."""
    if not ts_str:
        return None
    try:
        # Handle various ISO formats
        ts_str = ts_str.rstrip("Z")
        if "." in ts_str:
            # Truncate fractional seconds to 6 digits
            parts = ts_str.split(".")
            frac = parts[1][:6].ljust(6, "0")
            ts_str = f"{parts[0]}.{frac}"
        return datetime.fromisoformat(ts_str)
    except Exception as e:
        logger.debug(f"Failed to parse timestamp {ts_str}: {e}")
        return None


def _find_settle_before_frame(
    frame_timestamp: datetime,
    settle_events: List[PHD2SettleEvent],
    max_lookback_sec: float = 120.0,
) -> Optional[PHD2SettleEvent]:
    """
    Find the PHD2 settle event that completed just before this frame.

    Returns the most recent settle event within max_lookback_sec before frame_timestamp.
    """
    if not settle_events or not frame_timestamp:
        return None

    best_match: Optional[PHD2SettleEvent] = None
    best_gap = float("inf")

    for event in settle_events:
        event_ts = _parse_iso_timestamp(event.timestamp)
        if not event_ts:
            continue

        # Event must be before frame
        gap = (frame_timestamp - event_ts).total_seconds()
        if 0 < gap <= max_lookback_sec and gap < best_gap:
            best_gap = gap
            best_match = event

    return best_match


def _find_dither_before_frame(
    frame_timestamp: datetime,
    nina_segments: List[Dict[str, Any]],
    max_lookback_sec: float = 120.0,
) -> bool:
    """
    Check if there was a NINA dither event before this frame.

    Returns True if a dither segment ended within max_lookback_sec before frame_timestamp.
    """
    if not nina_segments or not frame_timestamp:
        return False

    for segment in nina_segments:
        if segment.get("label") != "dither":
            continue

        end_ts = _parse_iso_timestamp(segment.get("end", ""))
        if not end_ts:
            continue

        gap = (frame_timestamp - end_ts).total_seconds()
        if 0 < gap <= max_lookback_sec:
            return True

    return False


def _check_rms_event_during_frame(
    frame_timestamp: datetime,
    frame_duration: float,
    rms_events: List[Dict[str, Any]],
) -> bool:
    """
    Check if there was an RMS threshold event during frame exposure.
    """
    if not rms_events or not frame_timestamp:
        return False

    frame_end = frame_timestamp + timedelta(seconds=frame_duration)

    for event in rms_events:
        event_ts = _parse_iso_timestamp(event.get("ts", ""))
        if not event_ts:
            continue

        # Event during exposure window
        if frame_timestamp <= event_ts <= frame_end:
            return True

    return False


def _build_weather_lookup(
    weather_data: List[WeatherDataRecord],
) -> Dict[str, WeatherDataRecord]:
    """Build lookup dict from ExposureStartUTC to WeatherDataRecord."""
    lookup = {}
    for record in weather_data:
        if record.exposure_start_utc:
            lookup[record.exposure_start_utc] = record
    return lookup


def correlate_frames(
    image_metadata: List[ImageMetaDataRecord],
    weather_data: List[WeatherDataRecord],
    settle_events: List[PHD2SettleEvent],
    nina_analysis: Optional[Dict[str, Any]],
) -> List[CorrelatedFrame]:
    """
    Correlate ImageMetaData frames with other data sources by timestamp.

    Matching strategy:
    1. Weather: Exact match on ExposureStartUTC
    2. PHD2 Settle: Most recent settle within 120s before frame
    3. NINA Dither: Any dither segment ending within 120s before frame
    4. NINA RMS: Any RMS event during frame exposure
    """
    weather_lookup = _build_weather_lookup(weather_data)
    nina_segments = nina_analysis.get("segments", []) if nina_analysis else []
    rms_events = (
        nina_analysis.get("rms_analysis", {}).get("events", []) if nina_analysis else []
    )

    correlated = []

    for img in image_metadata:
        frame_ts = _parse_iso_timestamp(img.exposure_start_utc)

        # Match weather by exact timestamp
        weather = weather_lookup.get(img.exposure_start_utc)

        # Match PHD2 settle
        settle_event = _find_settle_before_frame(frame_ts, settle_events) if frame_ts else None

        # Check for dither before frame
        had_dither = _find_dither_before_frame(frame_ts, nina_segments) if frame_ts else False

        # Check for RMS event during frame
        had_rms_event = (
            _check_rms_event_during_frame(frame_ts, img.duration, rms_events)
            if frame_ts
            else False
        )

        correlated.append(
            CorrelatedFrame(
                exposure_number=img.exposure_number,
                timestamp_utc=img.exposure_start_utc,
                filter_name=img.filter_name,
                duration=img.duration,
                file_path=img.file_path,
                # Quality metrics
                hfr=img.hfr,
                hfr_stdev=img.hfr_stdev,
                detected_stars=img.detected_stars,
                guiding_rms_arcsec=img.guiding_rms_arcsec,
                # Focus data
                focuser_position=img.focuser_position,
                focuser_temp=img.focuser_temp,
                # Mount data
                airmass=img.airmass,
                pier_side=img.pier_side,
                # Weather (if matched)
                temperature=weather.temperature if weather else None,
                dew_point=weather.dew_point if weather else None,
                humidity=weather.humidity if weather else None,
                wind_speed=weather.wind_speed if weather else None,
                cloud_cover=weather.cloud_cover if weather else None,
                sky_temperature=weather.sky_temperature if weather else None,
                # PHD2 correlation
                phd2_settle_success=settle_event.success if settle_event else None,
                phd2_settle_time_sec=settle_event.settle_time_sec if settle_event else None,
                # NINA correlation
                nina_dither_before=had_dither,
                nina_rms_event=had_rms_event,
            )
        )

    return correlated


def build_session_summary(
    acquisition_details: Optional[AcquisitionDetails],
    image_metadata: List[ImageMetaDataRecord],
    weather_data: List[WeatherDataRecord],
    phd2_statistics: Optional[PHD2SettleStatistics],
    correlated_frames: List[CorrelatedFrame],
) -> Optional[SessionSummary]:
    """Build aggregate session summary from all sources."""
    if not image_metadata:
        return None

    # Basic info
    target_name = acquisition_details.target_name if acquisition_details else "Unknown"

    # Parse timestamps for session bounds
    timestamps = []
    for img in image_metadata:
        ts = _parse_iso_timestamp(img.exposure_start_utc)
        if ts:
            timestamps.append(ts)

    if not timestamps:
        return None

    timestamps.sort()
    session_start = timestamps[0]
    # Add last frame's duration for session end
    last_duration = image_metadata[-1].duration if image_metadata else 0
    session_end = timestamps[-1] + timedelta(seconds=last_duration)
    session_duration_hours = (session_end - session_start).total_seconds() / 3600

    # Frame counts by filter
    frames_by_filter: Dict[str, int] = defaultdict(int)
    for img in image_metadata:
        frames_by_filter[img.filter_name] += 1

    # Quality averages
    hfr_values = [img.hfr for img in image_metadata if img.hfr is not None]
    star_counts = [img.detected_stars for img in image_metadata if img.detected_stars is not None]
    guiding_rms_values = [
        img.guiding_rms_arcsec
        for img in image_metadata
        if img.guiding_rms_arcsec is not None and img.guiding_rms_arcsec > 0
    ]

    avg_hfr = statistics.mean(hfr_values) if hfr_values else None
    min_hfr = min(hfr_values) if hfr_values else None
    max_hfr = max(hfr_values) if hfr_values else None
    avg_star_count = statistics.mean(star_counts) if star_counts else None
    avg_guiding_rms = statistics.mean(guiding_rms_values) if guiding_rms_values else None

    # PHD2 stats
    phd2_settle_success_rate = phd2_statistics.success_rate if phd2_statistics else None
    phd2_avg_settle_time = phd2_statistics.avg_settle_time_sec if phd2_statistics else None
    phd2_total_settles = phd2_statistics.total_attempts if phd2_statistics else None

    # Weather summary
    temps = [w.temperature for w in weather_data if w.temperature is not None]
    humidities = [w.humidity for w in weather_data if w.humidity is not None]
    winds = [w.wind_speed for w in weather_data if w.wind_speed is not None]

    temp_min = min(temps) if temps else None
    temp_max = max(temps) if temps else None
    temp_avg = statistics.mean(temps) if temps else None
    humidity_avg = statistics.mean(humidities) if humidities else None
    wind_avg = statistics.mean(winds) if winds else None
    wind_max = max(winds) if winds else None

    # Equipment info
    telescope = acquisition_details.telescope_name if acquisition_details else None
    camera = acquisition_details.camera_name if acquisition_details else None
    focal_length = acquisition_details.focal_length if acquisition_details else None
    pixel_size = acquisition_details.pixel_size if acquisition_details else None

    # Calculate pixel scale if we have focal length and pixel size
    pixel_scale = None
    if focal_length and pixel_size:
        # Pixel scale (arcsec/pixel) = 206.265 * pixel_size(um) / focal_length(mm)
        pixel_scale = round(206.265 * pixel_size / focal_length, 2)

    return SessionSummary(
        target_name=target_name,
        session_date=session_start.strftime("%Y-%m-%d"),
        session_start=session_start.isoformat(),
        session_end=session_end.isoformat(),
        session_duration_hours=round(session_duration_hours, 2),
        total_frames=len(image_metadata),
        frames_by_filter=dict(frames_by_filter),
        avg_hfr=round(avg_hfr, 2) if avg_hfr else None,
        min_hfr=round(min_hfr, 2) if min_hfr else None,
        max_hfr=round(max_hfr, 2) if max_hfr else None,
        avg_star_count=round(avg_star_count, 0) if avg_star_count else None,
        avg_guiding_rms_arcsec=round(avg_guiding_rms, 2) if avg_guiding_rms else None,
        phd2_settle_success_rate=phd2_settle_success_rate,
        phd2_avg_settle_time_sec=phd2_avg_settle_time,
        phd2_total_settles=phd2_total_settles,
        temp_min=round(temp_min, 1) if temp_min is not None else None,
        temp_max=round(temp_max, 1) if temp_max is not None else None,
        temp_avg=round(temp_avg, 1) if temp_avg is not None else None,
        humidity_avg=round(humidity_avg, 1) if humidity_avg is not None else None,
        wind_avg=round(wind_avg, 1) if wind_avg is not None else None,
        wind_max=round(wind_max, 1) if wind_max is not None else None,
        telescope=telescope,
        camera=camera,
        focal_length=focal_length,
        pixel_scale=pixel_scale,
    )


def build_timelines(
    correlated_frames: List[CorrelatedFrame],
    image_metadata: List[ImageMetaDataRecord],
    weather_data: List[WeatherDataRecord],
) -> Dict[str, List[Dict[str, Any]]]:
    """Build time-series data for charts."""

    # HFR timeline
    hfr_timeline = []
    for frame in correlated_frames:
        if frame.hfr is not None:
            hfr_timeline.append(
                {
                    "timestamp": frame.timestamp_utc,
                    "hfr": round(frame.hfr, 2),
                    "filter": frame.filter_name,
                    "stars": frame.detected_stars,
                }
            )

    # Weather timeline
    weather_timeline = []
    for frame in correlated_frames:
        if frame.temperature is not None or frame.humidity is not None:
            weather_timeline.append(
                {
                    "timestamp": frame.timestamp_utc,
                    "temperature": frame.temperature,
                    "humidity": frame.humidity,
                    "wind_speed": frame.wind_speed,
                    "dew_point": frame.dew_point,
                    "sky_temp": frame.sky_temperature,
                }
            )

    # Focus timeline
    focus_timeline = []
    for frame in correlated_frames:
        if frame.focuser_position is not None:
            focus_timeline.append(
                {
                    "timestamp": frame.timestamp_utc,
                    "position": frame.focuser_position,
                    "focuser_temp": frame.focuser_temp,
                }
            )

    # Guiding timeline
    guiding_timeline = []
    for img in image_metadata:
        if img.guiding_rms_arcsec is not None and img.guiding_rms_arcsec > 0:
            guiding_timeline.append(
                {
                    "timestamp": img.exposure_start_utc,
                    "rms_total": round(img.guiding_rms_arcsec, 2) if img.guiding_rms_arcsec else None,
                    "rms_ra": round(img.guiding_rms_ra_arcsec, 2) if img.guiding_rms_ra_arcsec else None,
                    "rms_dec": round(img.guiding_rms_dec_arcsec, 2) if img.guiding_rms_dec_arcsec else None,
                }
            )

    return {
        "hfr": hfr_timeline,
        "weather": weather_timeline,
        "focus": focus_timeline,
        "guiding": guiding_timeline,
    }


def analyze_unified_session(
    nina_log_content: Optional[str] = None,
    phd2_debug_log_content: Optional[str] = None,
    session_metadata: Optional[SessionMetadataResponse] = None,
) -> UnifiedSessionAnalyzeResponse:
    """
    Perform unified session analysis combining multiple data sources.

    Args:
        nina_log_content: Content of NINA log file
        phd2_debug_log_content: Content of PHD2 debug log file
        session_metadata: Parsed Session Metadata (from directory or uploads)

    Returns:
        UnifiedSessionAnalyzeResponse with correlated analysis
    """
    try:
        # Parse NINA log if provided
        nina_analysis = None
        if nina_log_content:
            nina_analysis = parse_nina_log(nina_log_content)

        # Parse PHD2 debug log if provided
        phd2_statistics = None
        phd2_settle_events: List[PHD2SettleEvent] = []

        if phd2_debug_log_content:
            parser = PHD2DebugParser()
            settle_events, dither_commands, star_lost = parser.parse_log_content(
                phd2_debug_log_content
            )

            # Convert to model objects
            for event in settle_events:
                phd2_settle_events.append(
                    PHD2SettleEvent(
                        timestamp=event.timestamp.isoformat() if event.timestamp else "",
                        success=event.status == 0,
                        status=event.status,
                        total_frames=event.total_frames,
                        dropped_frames=event.dropped_frames,
                        settle_time_sec=event.settle_time_sec,
                        error=event.error,
                        failure_reason=event.failure_reason,
                    )
                )

            # Compute statistics
            if phd2_settle_events:
                successful = [e for e in phd2_settle_events if e.success]
                failed = [e for e in phd2_settle_events if not e.success]
                settle_times = [e.settle_time_sec for e in successful if e.settle_time_sec > 0]

                failure_reasons: Dict[str, int] = defaultdict(int)
                for e in failed:
                    reason = e.failure_reason or "other"
                    failure_reasons[reason] += 1

                frame_dist: Dict[int, int] = defaultdict(int)
                for e in successful:
                    frame_dist[e.total_frames] += 1

                phd2_statistics = PHD2SettleStatistics(
                    total_attempts=len(phd2_settle_events),
                    successful=len(successful),
                    failed=len(failed),
                    success_rate=round(len(successful) / len(phd2_settle_events) * 100, 1)
                    if phd2_settle_events
                    else 0.0,
                    avg_settle_time_sec=round(statistics.mean(settle_times), 2)
                    if settle_times
                    else 0.0,
                    min_settle_time_sec=round(min(settle_times), 2) if settle_times else 0.0,
                    max_settle_time_sec=round(max(settle_times), 2) if settle_times else 0.0,
                    median_settle_time_sec=round(statistics.median(settle_times), 2)
                    if settle_times
                    else 0.0,
                    frame_distribution=dict(frame_dist),
                    failure_reasons=dict(failure_reasons),
                )

        # Extract session metadata components
        acquisition_details = session_metadata.acquisition_details if session_metadata else None
        image_metadata = session_metadata.image_metadata if session_metadata else []
        weather_data = session_metadata.weather_data if session_metadata else []

        # Correlate frames
        correlated_frames = correlate_frames(
            image_metadata=image_metadata,
            weather_data=weather_data,
            settle_events=phd2_settle_events,
            nina_analysis=nina_analysis,
        )

        # Build summary
        summary = build_session_summary(
            acquisition_details=acquisition_details,
            image_metadata=image_metadata,
            weather_data=weather_data,
            phd2_statistics=phd2_statistics,
            correlated_frames=correlated_frames,
        )

        # Build timelines
        timelines = build_timelines(
            correlated_frames=correlated_frames,
            image_metadata=image_metadata,
            weather_data=weather_data,
        )

        return UnifiedSessionAnalyzeResponse(
            success=True,
            summary=summary,
            frames=correlated_frames,
            nina_analysis=nina_analysis,
            phd2_settle_statistics=phd2_statistics,
            phd2_settle_events=phd2_settle_events,
            hfr_timeline=timelines["hfr"],
            weather_timeline=timelines["weather"],
            focus_timeline=timelines["focus"],
            guiding_timeline=timelines["guiding"],
        )

    except Exception as e:
        logger.exception("Error in unified session analysis")
        return UnifiedSessionAnalyzeResponse(
            success=False,
            error=str(e),
        )
