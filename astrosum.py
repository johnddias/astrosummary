from pathlib import Path
from astropy.io import fits
from collections import defaultdict
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv

# Filter name to AstroBin filter ID mapping
FILTER_ID_MAP = {
    "R": 3007,
    "Ha": 4657,
    "OIII": 4746,
    "SII": 4838,
    "L": 3012,
    "G": 3011,
    "B": 3008
}

def get_filter_id(filt_name):
    return FILTER_ID_MAP.get(filt_name, "")

def extract_fits_metadata(fits_path):
    try:
        with fits.open(fits_path, ignore_missing_end=True) as hdul:
            hdr = hdul[0].header
            date_obs = hdr.get("DATE-OBS", None)
            filter_name = hdr.get("FILTER", "Unknown")
            exptime = hdr.get("EXPTIME", 0)
            
            if not date_obs:
                return None

            # Normalize date format to YYYY-MM-DD
            try:
                obs_date = datetime.fromisoformat(date_obs.split("T")[0]).strftime("%Y-%m-%d")
            except ValueError:
                return None

            return (obs_date, filter_name, float(exptime))
    except Exception:
        return None

def summarize_metadata(files):
    summary = defaultdict(lambda: defaultdict(lambda: {"counts": 0, "integration": 0.0}))

    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(extract_fits_metadata, f): f for f in files}

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing FITS files"):
            result = future.result()
            if result:
                date, filt, exptime = result
                summary[date][filt]["counts"] += 1
                summary[date][filt]["integration"] += exptime

    return summary

def write_astrobin_csv(summary, output_path):
    with open(output_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[
            "date", "filter", "number", "duration"
        ])
        writer.writeheader()
        for date, filters in summary.items():
            for filt, stats in filters.items():
                writer.writerow({
                    "date": date,
                    "filter": get_filter_id(filt),
                    "number": stats["counts"],
                    "duration": round(stats["integration"] / stats["counts"], 4) if stats["counts"] else 0
                })

if __name__ == "__main__":
    data_dir = Path(r"y:\M101FITS")  # <-- Change this to your input directory

    files = [f for ext in ("*.fits", "*.fit") for f in data_dir.rglob(ext)]

    summary = summarize_metadata(files)

    output_csv = "astrobin_acquisitions.csv"
    write_astrobin_csv(summary, output_csv)

    print(f"Summary written to {output_csv}")
