# AstroSummary

A fast and parallelized script to summarize astrophotography FITS subframes by night and filter, and export the results in a format compatible with [AstroBin's CSV acquisition import](https://www.astrobin.com/import-acquisition-from-csv/).

## Features

- Walks a directory tree for `.fits` and `.fit` files
- Extracts `DATE-OBS`, `FILTER`, and `EXPTIME` from FITS headers
- Groups and summarizes by date and filter
- Maps filters to AstroBin filter numeric IDs
- Outputs a clean CSV for import into AstroBin
- Supports multiprocessing and `tqdm` progress bar
- Works on Windows and Linux

## Installation

Create and activate a Python virtual environment (optional but recommended):

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate      # Windows
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Edit the script (`astrosum.py`) and set the path to your image directory:

```python
data_dir = Path(r"y:\M101")  # <-- Set your data folder here
```

2. Run the script:

```bash
python astrosum.py
```

3. The output CSV `astrobin_acquisitions.csv` will be created in the current working directory.

### Example Output

```csv
date,filter,number,duration
2024-04-15,3012,24,300.0
2024-04-15,4657,18,600.0
```

Each row corresponds to a date + filter combination with number of frames and per-frame exposure.

## Filter Mapping

The following filter names are recognized and mapped to AstroBin filter IDs:

| Filter | AstroBin ID |
|--------|-------------|
| R      | 3007        |
| Ha     | 4657        |
| OIII   | 4746        |
| SII    | 4838        |
| L      | 3012        |
| G      | 3011        |
| B      | 3008        |

Unrecognized filters will result in an empty `filter` field in the CSV. To add your own filters, look up your equipment in AstroBin and the ID will appear in the URL. For example:

https://app.astrobin.com/equipment/explorer/filter/3008/astronomik-deep-sky-blue-36mm

## Required FITS Header Keywords

Each FITS file must contain the following standard header keywords:

```fits
DATE-OBS = '2024-04-15T21:34:56.123' / Start of exposure (UTC ISO 8601 format)
FILTER   = 'Ha'                       / Filter name (must match mapping)
EXPTIME  = 600.0                      / Exposure time in seconds
```

Files missing any of these will be skipped automatically.

You can inspect FITS headers using:
- `astropy.io.fits` (Python)
- **fv** or **SAOImage DS9**
- **PixInsight** (FITS Header tool)
- **IRAF**, **FITS Liberator**

## Notes

- Script uses multiprocessing; on Windows it must be run from a script, not interactively.
- Compressed `.fz` files are not currently supported.

## License

MIT
