from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from models import (ScanRequest, ScanResponse, LightFrame, BackendSettings,
                    ValidationRequest, ValidationResponse, ValidationResult, QualityMetrics)
from scanner import scan_directory, stream_scan_directory
from fastapi.responses import StreamingResponse, Response
import json
from pathlib import Path
import sys
from fastapi import UploadFile, File, HTTPException
import csv
import io
from datetime import datetime

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

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("AstroSummary Backend starting up")
    logger.info("Validation endpoint available at /analyze/validate_rejections")
    logger.info("=" * 60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to log requests before Pydantic validation
@app.middleware("http")
async def log_requests(request, call_next):
    # Use print with flush to bypass logging buffering
    print(f"!!! MIDDLEWARE: {request.method} {request.url.path}", flush=True)

    if request.url.path == "/analyze/validate_rejections":
        print(f"=== VALIDATION: Content-Length={request.headers.get('content-length', 'unknown')} ===", flush=True)

    response = await call_next(request)

    if request.url.path == "/analyze/validate_rejections":
        print(f"=== DONE: status={response.status_code} ===", flush=True)

    return response

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
    logger.info(f"scan_stream called: path={req.path}, recurse={req.recurse}, extensions={req.extensions}")
    print(f"DEBUG main: scan_stream called with path={req.path}", file=sys.stderr, flush=True)
    print(f"DEBUG main: About to call stream_scan_directory", file=sys.stderr, flush=True)
    try:
        gen = stream_scan_directory(req.path, req.recurse, req.extensions)
        print(f"DEBUG main: Generator created, returning StreamingResponse", file=sys.stderr, flush=True)
        return StreamingResponse(gen, media_type='application/x-ndjson')
    except Exception as e:
        logger.exception("Error in scan_stream")
        print(f"DEBUG main: ERROR in scan_stream: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise


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


@app.post('/rejection/export_csv')
def export_rejected_frames_csv(request_data: dict):
    """Export rejected frames as CSV with target and filename columns."""
    from fastapi.responses import Response
    import csv
    import io

    def _is_frame_rejected(filename: str, rejected_filenames: set) -> bool:
        """
        Check if a frame is rejected, handling filename transformations.
        Same logic as scanner._is_frame_rejected()
        """
        if not rejected_filenames:
            return False

        # Direct match first
        if filename in rejected_filenames:
            return True

        # Try matching without extension
        name_without_ext = Path(filename).stem
        for rejected_name in rejected_filenames:
            rejected_stem = Path(rejected_name).stem
            if name_without_ext == rejected_stem:
                return True

        # Try matching with common calibration suffix patterns removed
        base_name = name_without_ext
        # Remove common suffixes that might be added during calibration
        calibration_suffixes = ['_c_lps', '_c', '_lps', '_cc', '_cal', '_calibrated']
        for suffix in calibration_suffixes:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]
                break

        # Also strip version numbers like _1, _2, _1_1, _1_2, etc. using regex
        import re
        base_name = re.sub(r'(_\d+)+$', '', base_name)

        # Check if any rejected file matches this base name
        for rejected_name in rejected_filenames:
            rejected_stem = Path(rejected_name).stem
            # Remove calibration suffixes from rejected names too
            rejected_base = rejected_stem
            for suffix in calibration_suffixes:
                if rejected_base.endswith(suffix):
                    rejected_base = rejected_base[:-len(suffix)]
                    break

            # Strip version numbers from rejected names too
            rejected_base = re.sub(r'(_\d+)+$', '', rejected_base)

            if base_name == rejected_base:
                return True

        return False

    try:
        frames_data = request_data.get('frames', [])
        rejection_data = request_data.get('rejection_data', {})

        rejected_filenames = set(rejection_data.get('rejected_frames', []))
        if not rejected_filenames:
            raise HTTPException(status_code=400, detail='No rejected frames found in rejection data')

        # Find matching frames using the same logic as the scanner
        rejected_frames_data = []
        for frame in frames_data:
            file_path = frame.get('file_path', '')
            if not file_path:
                continue

            filename = Path(file_path).name

            if _is_frame_rejected(filename, rejected_filenames):
                rejected_frames_data.append({
                    'target': frame.get('target') or 'Unknown',
                    'filename': filename
                })

        if not rejected_frames_data:
            raise HTTPException(status_code=400, detail='No matching rejected frames found in the scanned frames')

        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['target', 'filename'])
        writer.writeheader()
        writer.writerows(rejected_frames_data)

        csv_content = output.getvalue()

        return Response(
            content=csv_content,
            media_type='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename="rejected_frames.csv"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("CSV export error")
        raise HTTPException(status_code=500, detail=f'CSV export error: {e}')


@app.post('/analyze/test_validation_request')
async def test_validation_request(request: ValidationRequest):
    """
    Test endpoint to verify request parsing works without doing analysis.
    This helps isolate whether the issue is in Pydantic validation or analysis.
    """
    logger.info("=== TEST VALIDATION REQUEST ENDPOINT CALLED ===")
    logger.info(f"Received request with {len(request.frames)} frames")
    logger.info(f"Rejection data has {len(request.rejection_data.rejected_frames)} rejected frames")
    logger.info(f"PHD2 log path: {request.phd2_log_path}")

    return {
        "success": True,
        "frames_count": len(request.frames),
        "rejected_count": len(request.rejection_data.rejected_frames),
        "message": "Request parsed successfully"
    }


@app.post('/analyze/validate_rejections')
async def validate_rejections(request: Request):
    """
    Validate PixInsight WBPP rejections against objective quality metrics.

    Analyzes each frame for quality and compares against WBPP rejection status
    to identify false positives (good frames incorrectly rejected) and false
    negatives (bad frames that weren't rejected).

    NOTE: Uses raw Request to bypass slow Pydantic validation for large payloads
    """
    print("=== ENDPOINT: validate_rejections called ===", flush=True)

    # Parse JSON manually (fast)
    print("Parsing JSON body...", flush=True)
    body = await request.json()
    frames = body.get('frames', [])
    rejection_data = body.get('rejection_data', {})
    phd2_log_path = body.get('phd2_log_path')

    print(f"Received {len(frames)} frames", flush=True)

    try:
        print("Importing quality_analyzer...", flush=True)
        from quality_analyzer import SubframeAnalyzer
        print("quality_analyzer imported", flush=True)

        print("Importing phd2_log_parser...", flush=True)
        from phd2_log_parser import PHD2LogParser
        print("phd2_log_parser imported", flush=True)

        print("Importing scanner...", flush=True)
        from scanner import _is_frame_rejected
        print("All imports done", flush=True)

        print("Creating SubframeAnalyzer...", flush=True)
        analyzer = SubframeAnalyzer()
        print("Analyzer ready", flush=True)

        results = []

        # Parse PHD2 log(s) if provided
        guiding_data = {}
        if phd2_log_path:
            try:
                parser = PHD2LogParser()
                log_path = Path(phd2_log_path)

                # Check if it's a directory or a file
                if log_path.is_dir():
                    guiding_data = parser.parse_log_directory(phd2_log_path)
                    print(f"Loaded {len(guiding_data)} PHD2 samples from directory", flush=True)
                else:
                    guiding_data = parser.parse_log(phd2_log_path)
                    print(f"Loaded {len(guiding_data)} PHD2 samples from file", flush=True)
            except Exception as e:
                print(f"PHD2 log error: {e}", flush=True)

        # Build set of rejected filenames for fast lookup
        rejected_filenames = set(rejection_data.get('rejected_frames', []))

        print(f"Starting analysis of {len(frames)} frames...", flush=True)

        for idx, frame in enumerate(frames):
            try:
                # Log every 10th frame
                if idx % 10 == 0:
                    print(f"Progress: [{idx+1}/{len(frames)}]", flush=True)

                # Analyze frame quality
                metrics_obj = analyzer.analyze_frame(frame['file_path'])

                # Check if frame was rejected by WBPP
                filename = Path(frame['file_path']).name
                was_rejected = _is_frame_rejected(filename, rejected_filenames)

                # Correlate with PHD2 guiding if available
                if guiding_data and frame.get('date'):
                    try:
                        import re
                        frame_date_str = frame['date']
                        frame_time = None

                        # Try to extract time from filename pattern: _YYYY-MM-DD_HH-MM-SS_
                        time_match = re.search(r'_(\d{2})-(\d{2})-(\d{2})_', filename)
                        if time_match and len(frame_date_str) == 10:
                            # Found time in filename like _20-39-48_
                            h, m, s = time_match.groups()
                            frame_time = datetime.strptime(f"{frame_date_str} {h}:{m}:{s}", '%Y-%m-%d %H:%M:%S')
                        elif 'T' in frame_date_str:
                            # Full ISO format
                            frame_time = datetime.fromisoformat(frame_date_str.replace('Z', '+00:00'))

                        if frame_time:
                            parser = PHD2LogParser()
                            phd2_rms = parser.correlate_frame_to_guiding(
                                frame_time, frame.get('exposure_s', 0), guiding_data
                            )
                            if phd2_rms is not None:
                                metrics_obj.phd2_rms = phd2_rms
                    except Exception as e:
                        pass  # Silent fail for PHD2 correlation

                # Convert to Pydantic model
                metrics = QualityMetrics(
                    snr=metrics_obj.snr,
                    fwhm=metrics_obj.fwhm,
                    eccentricity=metrics_obj.eccentricity,
                    star_count=metrics_obj.star_count,
                    background_median=metrics_obj.background_median,
                    background_std=metrics_obj.background_std,
                    gradient_strength=metrics_obj.gradient_strength,
                    quality_score=metrics_obj.quality_score,
                    phd2_rms=getattr(metrics_obj, 'phd2_rms', None)
                )

                # Determine validation status
                # Threshold: quality_score >= 0.5 is "good"
                is_good_quality = metrics.quality_score >= 0.5

                if was_rejected and is_good_quality:
                    status = "FALSE_POSITIVE"  # Good frame incorrectly rejected
                elif was_rejected and not is_good_quality:
                    status = "CORRECT_REJECT"  # Bad frame correctly rejected
                elif not was_rejected and is_good_quality:
                    status = "CORRECT_ACCEPT"  # Good frame correctly accepted
                else:
                    status = "FALSE_NEGATIVE"  # Bad frame incorrectly accepted

                result = ValidationResult(
                    file_path=frame['file_path'],
                    filename=filename,
                    target=frame.get('target', 'Unknown'),
                    filter=frame.get('filter', 'Unknown'),
                    date=frame.get('date', ''),
                    rejected_by_wbpp=was_rejected,
                    metrics=metrics,
                    validation_status=status
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error analyzing {frame.get('file_path', 'unknown')}: {e}")
                continue

        # Compute summary statistics
        total = len(results)
        correct_rejects = sum(1 for r in results if r.validation_status == "CORRECT_REJECT")
        correct_accepts = sum(1 for r in results if r.validation_status == "CORRECT_ACCEPT")
        false_positives = sum(1 for r in results if r.validation_status == "FALSE_POSITIVE")
        false_negatives = sum(1 for r in results if r.validation_status == "FALSE_NEGATIVE")

        accuracy = (correct_rejects + correct_accepts) / total if total > 0 else 0.0

        summary = {
            'total_frames': total,
            'correct_rejects': correct_rejects,
            'correct_accepts': correct_accepts,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'accuracy': accuracy,
            'wbpp_reject_rate': sum(1 for r in results if r.rejected_by_wbpp) / total if total > 0 else 0.0,
            'mean_quality_rejected': sum(r.metrics.quality_score for r in results if r.rejected_by_wbpp) / max(1, sum(1 for r in results if r.rejected_by_wbpp)),
            'mean_quality_accepted': sum(r.metrics.quality_score for r in results if not r.rejected_by_wbpp) / max(1, sum(1 for r in results if not r.rejected_by_wbpp))
        }

        logger.info(f"=== VALIDATION COMPLETE ===")
        logger.info(f"Analyzed {total} frames: {correct_rejects} correct rejects, {correct_accepts} correct accepts")
        logger.info(f"False positives: {false_positives}, False negatives: {false_negatives}")
        logger.info(f"Accuracy: {accuracy:.1%}")

        response = ValidationResponse(results=results, summary=summary)
        logger.info(f"Returning response to client...")

        return response

    except Exception as e:
        logger.exception("Validation analysis error")
        raise HTTPException(status_code=500, detail=f'Validation error: {e}')


@app.post('/analyze/validate_rejections_stream')
async def validate_rejections_stream(request: Request):
    """
    SSE streaming version of validation endpoint.
    Streams progress updates and final results in real-time.
    Uses multi-threading for parallel frame analysis.
    """
    import concurrent.futures
    import os

    # Parse JSON BEFORE creating generator - request body must be read now
    body = await request.json()
    frames = body.get('frames', [])
    rejection_data = body.get('rejection_data', {})
    phd2_log_path = body.get('phd2_log_path')
    total_frames = len(frames)

    # Determine number of worker threads (use CPU count, max 8 to avoid overwhelming I/O)
    num_workers = min(os.cpu_count() or 4, 8)

    async def generate():
        try:

            # Send initial progress
            yield f"data: {json.dumps({'type': 'progress', 'current': 0, 'total': total_frames, 'status': f'Initializing ({num_workers} threads)...'})}\n\n"

            # Import modules
            from quality_analyzer import SubframeAnalyzer
            from phd2_log_parser import PHD2LogParser
            from scanner import _is_frame_rejected

            # Parse PHD2 logs if provided (do this once before parallelizing)
            guiding_data = {}
            if phd2_log_path:
                yield f"data: {json.dumps({'type': 'progress', 'current': 0, 'total': total_frames, 'status': 'Loading PHD2 logs...'})}\n\n"
                try:
                    parser = PHD2LogParser()
                    log_path = Path(phd2_log_path)
                    if log_path.is_dir():
                        guiding_data = parser.parse_log_directory(phd2_log_path)
                    else:
                        guiding_data = parser.parse_log(phd2_log_path)
                except Exception:
                    pass

            rejected_filenames = set(rejection_data.get('rejected_frames', []))

            def process_frame(frame):
                """Worker function to process a single frame"""
                try:
                    # Each thread gets its own analyzer instance
                    analyzer = SubframeAnalyzer()

                    # Analyze frame
                    metrics_obj = analyzer.analyze_frame(frame['file_path'])
                    filename = Path(frame['file_path']).name
                    was_rejected = _is_frame_rejected(filename, rejected_filenames)

                    # PHD2 correlation
                    if guiding_data and frame.get('date'):
                        try:
                            import re
                            frame_date_str = frame['date']
                            frame_time = None

                            time_match = re.search(r'_(\d{2})-(\d{2})-(\d{2})_', filename)
                            if time_match and len(frame_date_str) == 10:
                                h, m, s = time_match.groups()
                                frame_time = datetime.strptime(f"{frame_date_str} {h}:{m}:{s}", '%Y-%m-%d %H:%M:%S')
                            elif 'T' in frame_date_str:
                                frame_time = datetime.fromisoformat(frame_date_str.replace('Z', '+00:00'))

                            if frame_time:
                                phd2_parser = PHD2LogParser()
                                phd2_rms = phd2_parser.correlate_frame_to_guiding(
                                    frame_time, frame.get('exposure_s', 0), guiding_data
                                )
                                if phd2_rms is not None:
                                    metrics_obj.phd2_rms = phd2_rms
                        except Exception:
                            pass

                    # Build result
                    metrics = QualityMetrics(
                        snr=metrics_obj.snr,
                        fwhm=metrics_obj.fwhm,
                        eccentricity=metrics_obj.eccentricity,
                        star_count=metrics_obj.star_count,
                        background_median=metrics_obj.background_median,
                        background_std=metrics_obj.background_std,
                        gradient_strength=metrics_obj.gradient_strength,
                        quality_score=metrics_obj.quality_score,
                        phd2_rms=getattr(metrics_obj, 'phd2_rms', None)
                    )

                    is_good_quality = metrics.quality_score >= 0.5
                    if was_rejected and is_good_quality:
                        status = "FALSE_POSITIVE"
                    elif was_rejected and not is_good_quality:
                        status = "CORRECT_REJECT"
                    elif not was_rejected and is_good_quality:
                        status = "CORRECT_ACCEPT"
                    else:
                        status = "FALSE_NEGATIVE"

                    return ValidationResult(
                        file_path=frame['file_path'],
                        filename=filename,
                        target=frame.get('target', 'Unknown'),
                        filter=frame.get('filter', 'Unknown'),
                        date=frame.get('date', ''),
                        rejected_by_wbpp=was_rejected,
                        metrics=metrics,
                        validation_status=status
                    )

                except Exception as e:
                    return None

            results = []
            completed = 0

            yield f"data: {json.dumps({'type': 'progress', 'current': 0, 'total': total_frames, 'status': f'Analyzing frames ({num_workers} threads)...'})}\n\n"

            # Process frames in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit all frames for processing
                future_to_frame = {executor.submit(process_frame, frame): frame for frame in frames}

                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_frame):
                    completed += 1
                    result = future.result()
                    if result is not None:
                        results.append(result)

                    # Send progress update every 5 frames or on last frame to reduce SSE overhead
                    if completed % 5 == 0 or completed == total_frames:
                        yield f"data: {json.dumps({'type': 'progress', 'current': completed, 'total': total_frames, 'status': f'Analyzed {completed} of {total_frames} frames'})}\n\n"

            # Compute summary
            total = len(results)
            correct_rejects = sum(1 for r in results if r.validation_status == "CORRECT_REJECT")
            correct_accepts = sum(1 for r in results if r.validation_status == "CORRECT_ACCEPT")
            false_positives = sum(1 for r in results if r.validation_status == "FALSE_POSITIVE")
            false_negatives = sum(1 for r in results if r.validation_status == "FALSE_NEGATIVE")
            accuracy = (correct_rejects + correct_accepts) / total if total > 0 else 0.0

            summary = {
                'total_frames': total,
                'correct_rejects': correct_rejects,
                'correct_accepts': correct_accepts,
                'false_positives': false_positives,
                'false_negatives': false_negatives,
                'accuracy': accuracy,
                'wbpp_reject_rate': sum(1 for r in results if r.rejected_by_wbpp) / total if total > 0 else 0.0,
                'mean_quality_rejected': sum(r.metrics.quality_score for r in results if r.rejected_by_wbpp) / max(1, sum(1 for r in results if r.rejected_by_wbpp)),
                'mean_quality_accepted': sum(r.metrics.quality_score for r in results if not r.rejected_by_wbpp) / max(1, sum(1 for r in results if not r.rejected_by_wbpp))
            }

            # Send final complete message with results
            response = ValidationResponse(results=results, summary=summary)
            yield f"data: {json.dumps({'type': 'complete', 'data': response.model_dump()})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.post('/analyze/export_validation_csv')
def export_validation_csv(request: ValidationResponse):
    """Export validation results to CSV"""
    try:
        output = io.StringIO()
        fieldnames = [
            'filename', 'target', 'filter', 'date', 'rejected_by_wbpp',
            'quality_score', 'snr', 'fwhm', 'eccentricity', 'star_count',
            'gradient', 'phd2_rms', 'validation_status'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for result in request.results:
            writer.writerow({
                'filename': result.filename,
                'target': result.target,
                'filter': result.filter,
                'date': result.date,
                'rejected_by_wbpp': result.rejected_by_wbpp,
                'quality_score': f"{result.metrics.quality_score:.3f}",
                'snr': f"{result.metrics.snr:.2f}",
                'fwhm': f"{result.metrics.fwhm:.2f}",
                'eccentricity': f"{result.metrics.eccentricity:.3f}",
                'star_count': result.metrics.star_count,
                'gradient': f"{result.metrics.gradient_strength:.3f}",
                'phd2_rms': f"{result.metrics.phd2_rms:.2f}" if result.metrics.phd2_rms else '',
                'validation_status': result.validation_status
            })

        csv_content = output.getvalue()

        return Response(
            content=csv_content,
            media_type='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename="rejection_validation.csv"'
            }
        )

    except Exception as e:
        logger.exception("Validation CSV export error")
        raise HTTPException(status_code=500, detail=f'CSV export error: {e}')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
