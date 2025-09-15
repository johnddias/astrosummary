import os
import sys
from pathlib import Path

# Ensure the backend directory is on sys.path so `import scanner` works
HERE = Path(__file__).resolve().parent
BACKEND_DIR = str(HERE.parent)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from astropy.io import fits
from scanner import scan_directory, stream_scan_directory

BASE = Path(__file__).resolve().parent / 'tmp_scan_test'
if BASE.exists():
    import shutil
    shutil.rmtree(BASE)
BASE.mkdir(parents=True)

# create a light at root
light = BASE / 'light1.fits'
hdr = fits.Header()
hdr['IMAGETYP'] = 'LIGHT'
hdr['FILTER'] = 'Ha'
hdu = fits.PrimaryHDU(header=hdr)
hdu.writeto(light)

# create a subdir with a flat
sub = BASE / 'calib'
sub.mkdir()
flat = sub / 'flat1.fits'
hdr2 = fits.Header()
hdr2['IMAGETYP'] = 'FLAT'
hdr2['FILTER'] = 'Ha'
hdu2 = fits.PrimaryHDU(header=hdr2)
hdu2.writeto(flat)

print('Files created:')
for p in sorted(BASE.rglob('*.fits')):
    print(' -', p.relative_to(BASE))

print('\nRunning non-streaming scan_directory...')
frames, files_scanned, files_matched = scan_directory(str(BASE), True, ['.fits'])
print('scan_directory -> files_scanned=', files_scanned, 'files_matched=', files_matched)
print('frames:')
for f in frames:
    print(f)

print('\nRunning stream_scan_directory...')
for e in stream_scan_directory(str(BASE), True, ['.fits']):
    print(e.strip())
