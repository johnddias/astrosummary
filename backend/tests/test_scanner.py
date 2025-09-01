import os
import json
import tempfile
from pathlib import Path
import pytest
from astropy.io import fits

from scanner import _parse_filter, stream_scan_directory


def make_fits(path: str, header: dict = None):
    hdr = fits.Header()
    if header:
        for k, v in header.items():
            hdr[k] = v
    hdu = fits.PrimaryHDU(header=hdr)
    hdul = fits.HDUList([hdu])
    hdul.writeto(path, overwrite=True)


def test_parse_filter_header_variants(tmp_path):
    # FILTER key present
    p1 = tmp_path / "f1.fits"
    make_fits(str(p1), {"FILTER": "Hα"})
    assert _parse_filter(fits.getheader(str(p1)), str(p1)) == "Ha"

    # FILTER1 key
    p2 = tmp_path / "f2.fits"
    make_fits(str(p2), {"FILTER1": "OIII"})
    assert _parse_filter(fits.getheader(str(p2)), str(p2)) == "OIII"

    # no filter header, fallback to filename token
    p3 = tmp_path / "m42_Ha_001.fits"
    make_fits(str(p3), {})
    assert _parse_filter(fits.getheader(str(p3)), str(p3)) == "Ha"

    # unicode and spacing variations
    p4 = tmp_path / "m51 h α.fits"
    make_fits(str(p4), {})
    assert _parse_filter(fits.getheader(str(p4)), str(p4)) == "Ha"


def test_stream_scan_directory_yields_events(tmp_path):
    # create a mix of light and non-light frames
    p_light = tmp_path / "target_OIII_1.fits"
    make_fits(str(p_light), {"IMAGETYP": "LIGHT", "FILTER": "OIII"})

    p_dark = tmp_path / "dark.fits"
    make_fits(str(p_dark), {"IMAGETYP": "DARK"})

    # collect events from the generator
    gen = stream_scan_directory(str(tmp_path), True, [".fits"])
    events = list(gen)
    # parse JSON lines
    parsed = [json.loads(e) for e in events]

    # first event should be progress with total_files
    assert parsed[0]["type"] == "progress"
    assert "total_files" in parsed[0]
    total = parsed[0]["total_files"]
    assert total == 2

    # there must be at least one 'frame' event for the LIGHT file
    assert any(e.get("type") == "frame" for e in parsed)

    # final event should be done and include files_matched == 1
    assert parsed[-1]["type"] == "done"
    assert parsed[-1]["files_matched"] == 1
