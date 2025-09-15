from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ScanRequest, ScanResponse, LightFrame
from scanner import scan_directory, stream_scan_directory
from fastapi.responses import StreamingResponse
from models import BackendSettings
import json
from pathlib import Path
import sys
from fastapi import UploadFile, File, HTTPException

import logging


# module logger - create early so import-time issues can be logged
logger = logging.getLogger("backend.main")
if not logger.handlers:
    logging.basicConfig()


# Try to import the analyzer. When uvicorn is started from the `backend/` dir the
# repo root isn't on sys.path, so fall back to adding the parent directory where
# the script lives (repo root) to sys.path and retry.
try:
    from nina_session_analyzer import parse_nina_log
except Exception as exc:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from nina_session_analyzer import parse_nina_log
    except Exception as exc2:
        parse_nina_log = None
        logger.warning("nina_session_analyzer not importable: %s; started from %s", exc2, Path.cwd())

SETTINGS_FILE = Path(__file__).resolve().parent / 'settings.json'

def load_settings() -> BackendSettings:
    try:
        if SETTINGS_FILE.exists():
            return BackendSettings.parse_file(SETTINGS_FILE)
    except Exception:
        pass
    return BackendSettings()

def save_settings(s: BackendSettings):
    try:
        SETTINGS_FILE.write_text(s.json())
    except Exception:
        pass

app = FastAPI(title="AstroSummary Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/scan", response_model=ScanResponse)
def scan(req: ScanRequest):
    frames, files_scanned, files_matched = scan_directory(req.path, req.recurse, req.extensions)
    return {
        "frames": frames,
        "files_scanned": files_scanned,
        "files_matched": files_matched,
    }


@app.post('/scan_stream')
def scan_stream(req: ScanRequest):
    """Stream newline-delimited JSON events for long-running scans."""
    gen = stream_scan_directory(req.path, req.recurse, req.extensions)
    return StreamingResponse(gen, media_type='application/x-ndjson')


@app.post('/nina/analyze')
async def nina_analyze(file: UploadFile = File(...), download_gap_cap_s: float = 20.0):
    # log upload metadata so we always get at least one informative log line
    try:
        size = None
        if hasattr(file, 'filename'):
            fname = file.filename
        else:
            fname = '<unknown>'
        logger.info('nina_analyze request: filename=%s', fname)
    except Exception:
        logger.info('nina_analyze request: <could not inspect upload>')

    if parse_nina_log is None:
        logger.warning('nina_session_analyzer not available on server')
        raise HTTPException(status_code=500, detail='nina_session_analyzer not available on server')
    try:
        data = await file.read()
        text = data.decode('utf-8', errors='ignore')
        result = parse_nina_log(text, download_gap_cap_s=download_gap_cap_s)
        return result
    except Exception as e:
        # log full traceback to the server logs so the developer can see details
        logger.exception("nina_analyze error")
        raise HTTPException(status_code=500, detail=f'Analyzer error: {e}')


@app.get('/settings', response_model=BackendSettings)
def get_settings():
    return load_settings()


@app.post('/settings', response_model=BackendSettings)
def post_settings(s: BackendSettings):
    save_settings(s)
    return s
