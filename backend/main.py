from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ScanRequest, ScanResponse, LightFrame
from scanner import scan_directory, stream_scan_directory
from fastapi.responses import StreamingResponse
from models import BackendSettings
import json
from pathlib import Path

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


@app.get('/settings', response_model=BackendSettings)
def get_settings():
    return load_settings()


@app.post('/settings', response_model=BackendSettings)
def post_settings(s: BackendSettings):
    save_settings(s)
    return s
