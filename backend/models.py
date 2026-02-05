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


# PHD2 Settle Analysis Models

class PHD2SettleEvent(BaseModel):
    """A single settle completion event from PHD2"""
    timestamp: str  # ISO format
    success: bool
    status: int  # 0 = success, 1 = failure
    total_frames: int
    dropped_frames: int = 0
    settle_time_sec: float
    error: Optional[str] = None
    failure_reason: Optional[str] = None  # "timeout", "lost_star", "guiding_stopped", "other"


class PHD2DitherCommand(BaseModel):
    """A dither command sent to PHD2"""
    timestamp: str  # ISO format
    amount: float
    ra_only: bool
    settle_pixels: float
    settle_time: float
    settle_timeout: float


class PHD2SettleStatistics(BaseModel):
    """Aggregate statistics for settling performance"""
    total_attempts: int
    successful: int
    failed: int
    success_rate: float  # Percentage

    # Timing stats (successful settles only)
    avg_settle_time_sec: float
    min_settle_time_sec: float
    max_settle_time_sec: float
    median_settle_time_sec: float

    # Frame count distribution
    frame_distribution: Dict[int, int]

    # Failure breakdown
    failure_reasons: Dict[str, int]


class PHD2SessionStats(BaseModel):
    """Per-session statistics"""
    file: str
    date: str
    total: int
    successful: int
    failed: int
    success_rate: float


class PHD2AnalyzeRequest(BaseModel):
    """Request to analyze PHD2 debug logs"""
    path: str  # Path to debug log file or directory


class PHD2AnalyzeResponse(BaseModel):
    """Response from PHD2 debug log analysis"""
    success: bool
    error: Optional[str] = None
    statistics: Optional[PHD2SettleStatistics] = None
    sessions: List[PHD2SessionStats] = []
    events: List[PHD2SettleEvent] = []
    dithers: List[PHD2DitherCommand] = []


# =============================================================================
# Session Metadata Plugin Models
# =============================================================================

class AcquisitionDetails(BaseModel):
    """Equipment setup from Session Metadata Plugin (single record per session)"""
    target_name: str
    ra_coordinates: Optional[str] = None
    dec_coordinates: Optional[str] = None
    telescope_name: Optional[str] = None
    focal_length: Optional[float] = None  # mm
    focal_ratio: Optional[float] = None
    camera_name: Optional[str] = None
    pixel_size: Optional[float] = None  # microns
    bit_depth: Optional[int] = None
    observer_latitude: Optional[float] = None
    observer_longitude: Optional[float] = None
    observer_elevation: Optional[float] = None  # meters


class ImageMetaDataRecord(BaseModel):
    """Per-frame imaging data from Session Metadata Plugin"""
    exposure_number: int
    file_path: Optional[str] = None
    filter_name: str
    exposure_start: str  # Local time string
    exposure_start_utc: str  # ISO timestamp for correlation
    duration: float  # seconds
    binning: Optional[str] = None

    # Camera settings
    camera_temp: Optional[float] = None
    camera_target_temp: Optional[float] = None
    gain: Optional[int] = None
    offset: Optional[int] = None

    # Image statistics
    adu_mean: Optional[float] = None
    adu_median: Optional[float] = None
    adu_stdev: Optional[float] = None
    adu_min: Optional[int] = None
    adu_max: Optional[int] = None

    # Quality metrics
    hfr: Optional[float] = None
    hfr_stdev: Optional[float] = None
    detected_stars: Optional[int] = None
    fwhm: Optional[float] = None
    eccentricity: Optional[float] = None

    # Guiding data (from NINA)
    guiding_rms: Optional[float] = None
    guiding_rms_arcsec: Optional[float] = None
    guiding_rms_ra: Optional[float] = None
    guiding_rms_ra_arcsec: Optional[float] = None
    guiding_rms_dec: Optional[float] = None
    guiding_rms_dec_arcsec: Optional[float] = None

    # Focus data
    focuser_position: Optional[int] = None
    focuser_temp: Optional[float] = None
    rotator_position: Optional[float] = None

    # Mount data
    pier_side: Optional[str] = None
    airmass: Optional[float] = None
    mount_ra: Optional[float] = None
    mount_dec: Optional[float] = None
    image_type: Optional[str] = None


class WeatherDataRecord(BaseModel):
    """Per-frame environmental conditions from Session Metadata Plugin"""
    exposure_number: int
    exposure_start: str  # Local time string
    exposure_start_utc: str  # ISO timestamp for correlation
    temperature: Optional[float] = None  # Celsius
    dew_point: Optional[float] = None
    humidity: Optional[float] = None  # Percentage
    pressure: Optional[float] = None  # hPa
    wind_speed: Optional[float] = None  # m/s
    wind_direction: Optional[float] = None  # degrees
    wind_gust: Optional[float] = None
    cloud_cover: Optional[float] = None  # Percentage
    sky_temperature: Optional[float] = None  # Celsius
    sky_brightness: Optional[float] = None
    sky_quality: Optional[float] = None  # SQM reading


class SessionMetadataResponse(BaseModel):
    """Response from parsing Session Metadata files"""
    acquisition_details: Optional[AcquisitionDetails] = None
    image_metadata: List[ImageMetaDataRecord] = []
    weather_data: List[WeatherDataRecord] = []
    file_count: int = 0


# =============================================================================
# Unified Session Analysis Models
# =============================================================================

class CorrelatedFrame(BaseModel):
    """A single frame with correlated data from all sources"""
    # Core frame info (from ImageMetaData)
    exposure_number: int
    timestamp_utc: str
    filter_name: str
    duration: float
    file_path: Optional[str] = None

    # Quality metrics (from ImageMetaData)
    hfr: Optional[float] = None
    hfr_stdev: Optional[float] = None
    detected_stars: Optional[int] = None
    guiding_rms_arcsec: Optional[float] = None

    # Focus data (from ImageMetaData)
    focuser_position: Optional[int] = None
    focuser_temp: Optional[float] = None

    # Mount data
    airmass: Optional[float] = None
    pier_side: Optional[str] = None

    # Weather (from WeatherData - matched by timestamp)
    temperature: Optional[float] = None
    dew_point: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    cloud_cover: Optional[float] = None
    sky_temperature: Optional[float] = None

    # PHD2 correlation
    phd2_settle_success: Optional[bool] = None
    phd2_settle_time_sec: Optional[float] = None

    # NINA correlation
    nina_dither_before: Optional[bool] = None
    nina_rms_event: Optional[bool] = None


class SessionSummary(BaseModel):
    """Aggregate session summary from all sources"""
    # Basic info
    target_name: str
    session_date: str
    session_start: Optional[str] = None
    session_end: Optional[str] = None
    session_duration_hours: float

    # Frame counts
    total_frames: int
    frames_by_filter: Dict[str, int]

    # Quality averages
    avg_hfr: Optional[float] = None
    min_hfr: Optional[float] = None
    max_hfr: Optional[float] = None
    avg_star_count: Optional[float] = None
    avg_guiding_rms_arcsec: Optional[float] = None

    # PHD2 settle stats
    phd2_settle_success_rate: Optional[float] = None
    phd2_avg_settle_time_sec: Optional[float] = None
    phd2_total_settles: Optional[int] = None

    # Weather summary
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    temp_avg: Optional[float] = None
    humidity_avg: Optional[float] = None
    wind_avg: Optional[float] = None
    wind_max: Optional[float] = None

    # Equipment (from AcquisitionDetails)
    telescope: Optional[str] = None
    camera: Optional[str] = None
    focal_length: Optional[float] = None
    pixel_scale: Optional[float] = None  # arcsec/pixel


class TimelinePoint(BaseModel):
    """A single point in a timeline series"""
    timestamp: str
    value: float
    label: Optional[str] = None


class UnifiedSessionAnalyzeResponse(BaseModel):
    """Response from unified session analysis"""
    success: bool
    error: Optional[str] = None

    # Session summary
    summary: Optional[SessionSummary] = None

    # Correlated frame data
    frames: List[CorrelatedFrame] = []

    # Raw data from each source (for detailed views)
    nina_analysis: Optional[Dict[str, Any]] = None
    phd2_settle_statistics: Optional[PHD2SettleStatistics] = None
    phd2_settle_events: List[PHD2SettleEvent] = []

    # Time-series data for charts
    hfr_timeline: List[Dict[str, Any]] = []
    weather_timeline: List[Dict[str, Any]] = []
    focus_timeline: List[Dict[str, Any]] = []
    guiding_timeline: List[Dict[str, Any]] = []
