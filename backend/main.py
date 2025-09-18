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

# Try to import the rejection log parser
try:
    from rejection_log_parser import parse_rejection_log
except Exception as exc:
    parse_rejection_log = None
    logger.warning("rejection_log_parser not importable: %s", exc)

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
    scan_result = scan_directory(req.path, req.recurse, req.extensions)
    
    # Handle both old format (3 items) and new format (4 items with rejection data)
    if len(scan_result) == 4:
        frames, files_scanned, files_matched, rejection_data = scan_result
        return {
            "frames": frames,
            "files_scanned": files_scanned,
            "files_matched": files_matched,
            "rejection_data": rejection_data,
        }
    else:
        frames, files_scanned, files_matched = scan_result
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


@app.post('/rejection/parse')
async def parse_rejection_log_endpoint(file: UploadFile = File(...)):
    """Parse an uploaded ProcessLogger.txt or similar rejection log file."""
    try:
        # Log upload metadata
        fname = getattr(file, 'filename', '<unknown>')
        logger.info('rejection log parse request: filename=%s', fname)
        
        if parse_rejection_log is None:
            logger.warning('rejection_log_parser not available on server')
            raise HTTPException(status_code=500, detail='rejection_log_parser not available on server')
        
        # Read and decode file content
        data = await file.read()
        text = data.decode('utf-8', errors='ignore')
        
        # Save to temporary file for parser (it expects a file path)
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            tmp_file.write(text)
            tmp_path = tmp_file.name
        
        try:
            result = parse_rejection_log(tmp_path)
            result['original_filename'] = fname
            return result
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)
            
    except Exception as e:
        logger.exception("rejection log parse error")
        raise HTTPException(status_code=500, detail=f'Rejection log parse error: {e}')


@app.post('/rejection/apply')
def apply_rejection_filter(scan_data: dict, rejection_data: dict):
    """Apply rejection filter to scan data, removing rejected frames from totals."""
    try:
        rejected_filenames = set(rejection_data.get('rejected_frames', []))
        if not rejected_filenames:
            return scan_data  # No rejections to apply
        
        # Create a copy of scan data to modify
        filtered_data = scan_data.copy()
        
        # Filter frames array
        if 'frames' in filtered_data:
            original_count = len(filtered_data['frames'])
            filtered_frames = []
            
            for frame in filtered_data['frames']:
                filename = Path(frame.get('file_path', '')).name
                if filename not in rejected_filenames:
                    filtered_frames.append(frame)
            
            filtered_data['frames'] = filtered_frames
            filtered_data['rejection_info'] = {
                'original_frame_count': original_count,
                'filtered_frame_count': len(filtered_frames),
                'rejected_frame_count': original_count - len(filtered_frames),
                'rejection_log': rejection_data.get('log_path', 'uploaded'),
                'applied': True
            }
        
        return filtered_data
        
    except Exception as e:
        logger.exception("rejection filter apply error")
        raise HTTPException(status_code=500, detail=f'Rejection filter error: {e}')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
