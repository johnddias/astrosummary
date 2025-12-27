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


class QualityMetrics(BaseModel):
    """Quality metrics for a single sub-frame"""
    snr: float
    fwhm: float
    eccentricity: float
    star_count: int
    background_median: float
    background_std: float
    gradient_strength: float
    quality_score: float
    phd2_rms: Optional[float] = None  # Optional guiding RMS


class ValidationResult(BaseModel):
    """Result of validating a frame against PixInsight rejection"""
    file_path: str
    filename: str
    target: str
    filter: str
    date: str
    rejected_by_wbpp: bool
    metrics: QualityMetrics
    validation_status: str  # "CORRECT_REJECT", "CORRECT_ACCEPT", "FALSE_POSITIVE", "FALSE_NEGATIVE"


class ValidationRequest(BaseModel):
    """Request to validate PixInsight rejections"""
    frames: List[LightFrame]
    rejection_data: RejectionData
    phd2_log_path: Optional[str] = None


class ValidationResponse(BaseModel):
    """Response from validation analysis"""
    results: List[ValidationResult]
    summary: Dict[str, Any]  # Statistics about validation
