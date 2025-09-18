from pydantic import BaseModel
from typing import Literal, Optional, Dict, List, Any

FrameType = Literal["LIGHT", "DARK", "FLAT", "BIAS", "OTHER"]

class LightFrame(BaseModel):
    target: str
    filter: str
    exposure_s: float
    date: str              # YYYY-MM-DD
    frameType: FrameType
    file_path: Optional[str] = None
    rejected: Optional[bool] = None

class RejectionData(BaseModel):
    rejected_frames: List[str]
    quality_data: Dict[str, Any]
    rejection_logs: List[str]
    rejected_count: int

class ScanRequest(BaseModel):
    path: str              # e.g. r"Y:\M101" or "/data/m101"
    recurse: bool = True
    extensions: List[str] = [".fit", ".fits"]  # case-insensitive

class ScanResponse(BaseModel):
    frames: List[LightFrame]
    files_scanned: int
    files_matched: int
    rejection_data: Optional[RejectionData] = None


class BackendSettings(BaseModel):
    path: str = ''
    recurse: bool = True
