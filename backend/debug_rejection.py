#!/usr/bin/env python3
"""
Debug script to test rejection log detection and parsing.
"""

import sys
from pathlib import Path
from scanner import _find_rejection_logs, _parse_rejection_logs

def debug_rejection_detection(scan_path: str):
    """Test rejection log detection in a directory."""
    print(f"=== Testing rejection detection in: {scan_path} ===")
    
    # Check if path exists
    if not Path(scan_path).exists():
        print(f"ERROR: Path does not exist: {scan_path}")
        return
    
    # Find rejection logs
    print("\n1. Looking for rejection logs...")
    rejection_logs = _find_rejection_logs(scan_path, recurse=True)
    print(f"Found rejection logs: {rejection_logs}")
    
    if not rejection_logs:
        print("No rejection logs found. Checking for files manually...")
        for pattern in ["ProcessLogger.txt", "processlogger.txt"]:
            matches = list(Path(scan_path).rglob(pattern))
            print(f"  {pattern}: {matches}")
        return
    
    # Parse rejection logs
    print("\n2. Parsing rejection logs...")
    rejection_data = _parse_rejection_logs(rejection_logs)
    
    if rejection_data:
        print(f"Rejection data found:")
        print(f"  Rejected frames: {len(rejection_data.get('rejected_frames', []))}")
        print(f"  First few rejected: {rejection_data.get('rejected_frames', [])[:5]}")
        print(f"  Quality data entries: {len(rejection_data.get('quality_data', {}))}")
    else:
        print("No rejection data parsed from logs")
    
    print("\n3. Testing individual log parsing...")
    for log_path in rejection_logs:
        print(f"\nParsing: {log_path}")
        try:
            from rejection_log_parser import parse_rejection_log
            result = parse_rejection_log(log_path)
            print(f"  Rejected count: {result.get('rejected_count', 0)}")
            print(f"  Total frames mentioned: {result.get('total_frames_mentioned', 0)}")
            print(f"  Acceptance rate: {result.get('acceptance_rate', 0):.2%}")
            if result.get('rejected_frames'):
                print(f"  Sample rejected files: {result['rejected_frames'][:3]}")
        except Exception as e:
            print(f"  ERROR parsing log: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_rejection.py <scan_directory>")
        print("Example: python debug_rejection.py 'D:\\Astro Processing\\Stacked\\Sh2-132 Mosaic'")
    else:
        debug_rejection_detection(sys.argv[1])