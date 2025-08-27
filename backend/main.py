from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ScanRequest, ScanResponse, LightFrame
from scanner import scan_directory

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
