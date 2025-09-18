"""
ProcessLogger.txt rejection log parser.

Parses stacking software logs to extract rejected frame information.
Supports common formats from PixInsight, DeepSkyStacker, and similar tools.
"""

import re
from typing import List, Dict, Set, Optional
from pathlib import Path
from datetime import datetime

class RejectionLogParser:
    """Parse ProcessLogger.txt files to extract rejected frame information."""
    
    def __init__(self):
        # Common rejection patterns for different stacking software
        self.rejection_patterns = [
            # PixInsight: capture everything inside brackets ending with .xisf
            r"\[([^\]]+\.xisf)",
            # DeepSkyStacker and generic patterns (keep as fallback)
            r".*rejected.*?([\w\s\-\.]+\.(?:fit|fits|fts|tif|tiff|xisf)).*",
            r".*Rejection.*?([\w\s\-\.]+\.(?:fit|fits|fts|tif|tiff|xisf)).*",
            r".*(?:reject|discard|exclude).*?([\w\s\-\.]+\.(?:fit|fits|fts|tif|tiff|xisf)).*",
        ]
        
        # Patterns for quality metrics that might indicate rejection
        self.quality_patterns = [
            r".*([^\s]+\.(?:fit|fits|fts|xisf)).*(?:quality|score|fwhm|noise).*?([0-9.]+).*",
            r".*([^\s]+\.(?:fit|fits|fts|xisf)).*stars.*?([0-9]+).*",
        ]
    
    def _normalize_filename(self, filename: str) -> str:
        """
        Normalize calibrated filenames to match raw filenames.
        
        PixInsight calibration often adds suffixes like '_c_lps' and changes extensions.
        Examples:
        - 'M42_Ha_001_c_lps.xisf' -> 'M42_Ha_001.fit'
        - 'NGC1333_OIII_005_c_lps.xisf' -> 'NGC1333_OIII_005.fits'
        
        Returns a single normalized name - the matching logic in scanner 
        will handle trying different extensions.
        """
        if not filename:
            return filename
            
        # Remove path and get just the filename
        base_name = Path(filename).name
        
        # Remove common PixInsight calibration suffixes
        calibration_suffixes = ['_c_lps', '_c', '_lps', '_cc', '_cal', '_calibrated']
        for suffix in calibration_suffixes:
            if suffix in base_name:
                base_name = base_name.replace(suffix, '')
        
        # Change extension from .xisf to most common FITS extension
        if base_name.lower().endswith('.xisf'):
            # Use .fit as the default normalized extension
            base_without_ext = base_name[:-5]  # Remove .xisf
            return f"{base_without_ext}.fit"
        
        return base_name
    
    def parse_log(self, log_path: str) -> Dict:
        """
        Parse a ProcessLogger.txt file and extract rejection information.
        
        Returns:
            Dict with rejected_frames, quality_data, and summary stats
        """
        log_path = Path(log_path)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")
        
        rejected_frames = set()
        quality_data = {}
        all_frames = set()
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check for rejected frames
                for pattern in self.rejection_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        raw_filename = match.group(1)
                        normalized_name = self._normalize_filename(raw_filename)
                        rejected_frames.add(normalized_name)
                        break
                
                # Extract quality metrics
                for pattern in self.quality_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        raw_filename = match.group(1)
                        metric_value = float(match.group(2))
                        
                        # Normalize filename for quality data too
                        filename = self._normalize_filename(raw_filename)
                        all_frames.add(filename)
                        
                        if filename not in quality_data:
                            quality_data[filename] = {}
                        
                        # Determine metric type from line content
                        if 'fwhm' in line.lower():
                            quality_data[filename]['fwhm'] = metric_value
                        elif 'noise' in line.lower():
                            quality_data[filename]['noise'] = metric_value
                        elif 'quality' in line.lower() or 'score' in line.lower():
                            quality_data[filename]['quality'] = metric_value
                        elif 'stars' in line.lower():
                            quality_data[filename]['stars'] = int(metric_value)
        
        except Exception as e:
            raise Exception(f"Error parsing log file: {e}")
        
        return {
            'rejected_frames': list(rejected_frames),
            'quality_data': quality_data,
            'total_frames_mentioned': len(all_frames),
            'rejected_count': len(rejected_frames),
            'acceptance_rate': (len(all_frames) - len(rejected_frames)) / len(all_frames) if all_frames else 1.0,
            'log_path': str(log_path)
        }
    
    def get_rejected_frame_patterns(self, target_name: str = None, filter_name: str = None) -> Set[str]:
        """
        Generate filename patterns for rejected frames based on target and filter.
        
        This helps match rejection log entries to FITS files in the scan.
        """
        patterns = set()
        
        if target_name and filter_name:
            # Common naming patterns
            patterns.update([
                f"*{target_name}*{filter_name}*.fit*",
                f"*{target_name}*{filter_name}*.FIT*",
                f"*{filter_name}*{target_name}*.fit*",
                f"*{filter_name}*{target_name}*.FIT*",
            ])
        
        return patterns

def parse_rejection_log(log_path: str) -> Dict:
    """Convenience function to parse a rejection log."""
    parser = RejectionLogParser()
    return parser.parse_log(log_path)

if __name__ == "__main__":
    # Test the parser
    import sys
    if len(sys.argv) > 1:
        log_path = sys.argv[1]
        try:
            result = parse_rejection_log(log_path)
            print(f"Parsed rejection log: {log_path}")
            print(f"Rejected frames: {result['rejected_count']}")
            print(f"Total frames mentioned: {result['total_frames_mentioned']}")
            print(f"Acceptance rate: {result['acceptance_rate']:.2%}")
            print(f"Rejected files: {result['rejected_frames']}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python rejection_log_parser.py <log_file_path>")