"""
PHD2 Guide Log Parser

Parses PHD2 guiding logs to extract RMS tracking performance
for correlation with sub-frame quality.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger("backend.phd2_log_parser")


@dataclass
class GuidingMetrics:
    """Guiding metrics for a time period"""
    timestamp: datetime
    rms_total: float
    rms_ra: float
    rms_dec: float


class PHD2LogParser:
    """Parser for PHD2 guide logs"""

    def __init__(self):
        pass

    def parse_log_directory(self, log_dir: str) -> Dict[datetime, GuidingMetrics]:
        """
        Parse all PHD2 guide logs in a directory and merge them

        Args:
            log_dir: Path to directory containing PHD2 guide log files

        Returns:
            Dictionary mapping timestamp to GuidingMetrics from all logs
        """
        log_path = Path(log_dir)
        if not log_path.exists() or not log_path.is_dir():
            logger.error(f"PHD2 log directory not found: {log_dir}")
            return {}

        all_guiding_data = {}

        # Find all guide log files (PHD2_GuideLog_*.txt or *.csv)
        log_files = list(log_path.glob("PHD2_GuideLog_*.txt")) + list(log_path.glob("*.csv"))

        if not log_files:
            logger.warning(f"No PHD2 log files found in {log_dir}")
            return {}

        logger.info(f"Found {len(log_files)} PHD2 log files in {log_dir}")

        for log_file in sorted(log_files):
            try:
                file_data = self.parse_log(str(log_file))
                all_guiding_data.update(file_data)
                logger.info(f"Loaded {len(file_data)} samples from {log_file.name}")
            except Exception as e:
                logger.warning(f"Failed to parse {log_file.name}: {e}")
                continue

        print(f"PHD2: Total guiding samples loaded: {len(all_guiding_data)}", flush=True)
        return all_guiding_data

    def parse_log(self, log_path: str) -> Dict[datetime, GuidingMetrics]:
        """
        Parse PHD2 guide log file

        PHD2 log format (CSV):
        Frame,Time,mount,dx,dy,RARawDistance,DECRawDistance,RAGuideDistance,DECGuideDistance,...

        Args:
            log_path: Path to PHD2 guide log file

        Returns:
            Dictionary mapping timestamp to GuidingMetrics
        """
        log_file = Path(log_path)
        if not log_file.exists():
            logger.error(f"PHD2 log not found: {log_path}")
            return {}

        guiding_data = {}

        try:
            import re

            with open(log_file, 'r', encoding='utf-8') as f:
                # PHD2 logs have header lines before the CSV data
                # Extract start datetime from "Guiding Begins at" line
                header_line = None
                guiding_start_time = None

                for line in f:
                    # Look for "Guiding Begins at 2025-12-25 16:14:10"
                    if guiding_start_time is None and 'Guiding Begins at' in line:
                        dt_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                        if dt_match:
                            try:
                                guiding_start_time = datetime.strptime(dt_match.group(1), '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                pass

                    if line.startswith('Frame,'):
                        header_line = line
                        break

                if not header_line:
                    logger.warning(f"No CSV header found in {log_path}")
                    return {}

                if guiding_start_time is None:
                    logger.warning(f"Could not find guiding start time in {log_path}")
                    return {}

                # Parse remaining lines as CSV using the header we found
                import io
                remaining_content = header_line + f.read()
                reader = csv.DictReader(io.StringIO(remaining_content))

                for row in reader:
                    try:
                        # Parse timestamp - PHD2 Time column is just time, not datetime
                        time_str = row.get('Time') or ''
                        time_str = time_str.strip()

                        if not time_str:
                            continue

                        # Time column is elapsed seconds since guiding started
                        # Skip non-numeric values like "Settling started"
                        try:
                            elapsed_seconds = float(time_str)
                        except ValueError:
                            continue

                        # Calculate actual timestamp
                        timestamp = guiding_start_time + timedelta(seconds=elapsed_seconds)

                        # Extract RA and DEC distances (in pixels or arcsec depending on log)
                        ra_raw = float(row.get('RARawDistance', 0) or 0)
                        dec_raw = float(row.get('DECRawDistance', 0) or 0)

                        # Compute total RMS
                        rms_total = (ra_raw**2 + dec_raw**2)**0.5

                        metrics = GuidingMetrics(
                            timestamp=timestamp,
                            rms_total=rms_total,
                            rms_ra=abs(ra_raw),
                            rms_dec=abs(dec_raw)
                        )

                        guiding_data[timestamp] = metrics

                    except (ValueError, KeyError) as e:
                        # Skip malformed rows
                        continue

            logger.info(f"Parsed {len(guiding_data)} guiding samples from {log_path}")
            return guiding_data

        except Exception as e:
            logger.error(f"Error parsing PHD2 log {log_path}: {e}")
            return {}

    def correlate_frame_to_guiding(
        self,
        frame_timestamp: datetime,
        exposure_seconds: float,
        guiding_data: Dict[datetime, GuidingMetrics],
        tolerance_seconds: float = 30.0
    ) -> Optional[float]:
        """
        Correlate a frame's exposure time with guiding performance

        Args:
            frame_timestamp: Timestamp of frame (from FITS header)
            exposure_seconds: Exposure duration
            guiding_data: Dictionary of guiding metrics from log
            tolerance_seconds: Time tolerance for finding matching guiding data

        Returns:
            Mean RMS during exposure, or None if no match
        """
        if not guiding_data:
            return None

        # Define exposure window
        exposure_start = frame_timestamp
        exposure_end = frame_timestamp + timedelta(seconds=exposure_seconds)

        # Find all guiding samples within exposure window
        matching_samples = []
        for ts, metrics in guiding_data.items():
            # Check if timestamp is within exposure window (with tolerance)
            if (exposure_start - timedelta(seconds=tolerance_seconds) <= ts <=
                exposure_end + timedelta(seconds=tolerance_seconds)):
                matching_samples.append(metrics.rms_total)

        if matching_samples:
            # Return mean RMS during exposure
            return sum(matching_samples) / len(matching_samples)

        return None


def parse_phd2_log(log_path: str) -> Dict[str, any]:
    """
    Convenience function to parse PHD2 log and return structured data

    Returns:
        Dictionary with guiding data and statistics
    """
    parser = PHD2LogParser()
    guiding_data = parser.parse_log(log_path)

    if not guiding_data:
        return {
            'success': False,
            'error': 'Failed to parse log or no data found',
            'sample_count': 0
        }

    # Compute summary statistics
    all_rms = [m.rms_total for m in guiding_data.values()]
    all_ra = [m.rms_ra for m in guiding_data.values()]
    all_dec = [m.rms_dec for m in guiding_data.values()]

    import numpy as np

    return {
        'success': True,
        'sample_count': len(guiding_data),
        'rms_stats': {
            'total_mean': float(np.mean(all_rms)),
            'total_median': float(np.median(all_rms)),
            'total_std': float(np.std(all_rms)),
            'ra_mean': float(np.mean(all_ra)),
            'dec_mean': float(np.mean(all_dec))
        },
        'time_range': {
            'start': min(guiding_data.keys()).isoformat(),
            'end': max(guiding_data.keys()).isoformat()
        },
        'guiding_data': {ts.isoformat(): {
            'rms_total': m.rms_total,
            'rms_ra': m.rms_ra,
            'rms_dec': m.rms_dec
        } for ts, m in guiding_data.items()}
    }
