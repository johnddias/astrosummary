from collections import defaultdict
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET

data_dir = Path(r"Y:\M101")

# New structure: {date: {filter: {"counts": int, "integration": float}}}
summary = defaultdict(lambda: defaultdict(lambda: {"counts": 0, "integration": 0.0}))

def extract_metadata(file):
    try:
        tree = ET.parse(file)
        root = tree.getroot()
        props = {p.attrib['id']: p.text for p in root.findall(".//Property")}
        filter_ = props.get("FILTER", "Unknown")
        exp = float(props.get("EXPOSURE", 0))
        date_obs = props.get("DATE-OBS") or props.get("DATE")
        if date_obs:
            date_str = datetime.fromisoformat(date_obs).date().isoformat()
            return date_str, filter_, exp
    except Exception:
        pass
    return None, None, None

for f in data_dir.rglob("*.xisf"):
    date, filt, exp = extract_metadata(f)
    if date and filt and exp:
        summary[date][filt]["counts"] += 1
        summary[date][filt]["integration"] += exp

# Output
for date, filters in sorted(summary.items()):
    print(f"Date: {date}")
    for filt, stats in filters.items():
        count = stats["counts"]
        integration = stats["integration"]
        print(f"  Filter: {filt}")
        print(f"    Frames: {count}")
        print(f"    Total integration: {integration:.1f}s ({integration/60:.1f} minutes)")
