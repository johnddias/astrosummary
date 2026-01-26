# AstroSummary Project

## Project Overview
Full-stack web application for analyzing astrophotography imaging sessions.
- **Backend**: Python FastAPI (port 8000)
- **Frontend**: React/TypeScript with Vite (port 3001)

## PHD2 Log Analysis Enhancement (TODO)

### Current Implementation
- `backend/phd2_log_parser.py` - Parses PHD2 Guide Logs (CSV format) for RMS values
- `backend/nina_session_analyzer.py` - Parses NINA logs, detects dither events

### Enhancement: PHD2 Debug Log Parsing

PHD2 generates two log types:
1. **Guide Log** (`PHD2_GuideLog_*.txt`) - CSV with frame-by-frame guiding data (already parsed)
2. **Debug Log** (`PHD2_DebugLog_*.txt`) - Detailed JSON events including settling (NOT YET PARSED)

#### Debug Log Format (key events to extract)

**Dither Command** (from NINA):
```json
{"method":"dither","params":{"amount":5,"raOnly":false,"settle":{"pixels":1.5,"time":10,"timeout":60}}}
```

**Settling Progress**:
```json
{"Event":"Settling","Distance":0.85,"Time":2.7,"SettleTime":10.0,"StarLocked":true}
```

**Settle Complete**:
```json
{"Event":"SettleDone","Status":0,"TotalFrames":8,"DroppedFrames":0}
{"Event":"SettleDone","Status":1,"Error":"timed-out waiting for guider to settle","TotalFrames":12}
```

#### Key Metrics to Extract
- **Settle success rate**: Status 0 = success, Status 1 = failure
- **Average settle time**: `TotalFrames × ~2.6s` (frame time)
- **Failure reasons**: "timed-out", "failed to find guide star", "Guiding stopped"
- **Settle parameters**: pixels threshold, time requirement, timeout

#### Typical Values (from user's logs - 23 days of data)
- Total settle attempts: 1,213
- Success rate: 75.3% (913 successful)
- Average successful settle: ~18 seconds (6.85 frames)
- 72% complete in 5-6 frames (13-16 seconds)
- Failure breakdown: 80% timeout, 17% lost star, 3% guiding stopped

### Correlation Points (NINA ↔ PHD2)

Match timestamps between:
1. NINA dither command → PHD2 dither receipt → PHD2 SettleDone
2. Calculate actual settle duration per dither
3. Correlate settle failures with rejected frames

### Implementation Tasks

1. **Add PHD2 Debug Log Parser** (`backend/phd2_debug_parser.py`)
   - Parse JSON events from debug log
   - Extract SettleDone events with Status, TotalFrames, Error
   - Extract dither commands with settle parameters
   - Handle multiple sessions per log file

2. **Add Data Models** (`backend/models.py`)
   ```python
   @dataclass
   class SettleEvent:
       timestamp: datetime
       status: int  # 0=success, 1=failure
       total_frames: int
       error: Optional[str]
       settle_time_sec: float  # calculated from TotalFrames

   @dataclass
   class SettleStatistics:
       total_attempts: int
       successful: int
       failed: int
       success_rate: float
       avg_settle_time_sec: float
       failure_reasons: Dict[str, int]
   ```

3. **Add API Endpoint** (`backend/main.py`)
   - `POST /phd2/analyze` - Upload and analyze PHD2 debug log
   - Return settle statistics and per-event details

4. **Add Frontend Visualization** (`astrosummary-ui/src/pages/`)
   - Settle success rate chart
   - Settle time distribution histogram
   - Failure reason breakdown
   - Per-session comparison

5. **Correlation with NINA** (enhance `nina_session_analyzer.py`)
   - Match NINA dither events with PHD2 SettleDone timestamps
   - Flag frames captured during/after settle failures

### User's Setup Reference
- Imaging: ASI2600MM Pro + Askar 140APO + 0.8x reducer (784mm FL, 0.99"/px)
- Guiding: ASI290MM Mini + 50mm guidescope (250mm FL, 2.39"/px)
- Dither amount: 5 pixels (~12 arcsec)
- Settle params: 1.5 px threshold, 10s time, 60s timeout

### Files to Modify
- `backend/phd2_log_parser.py` - Add debug log parsing
- `backend/models.py` - Add SettleEvent, SettleStatistics models
- `backend/main.py` - Add /phd2/analyze endpoint
- `astrosummary-ui/src/pages/NinaAnalyzer.tsx` - Add settle statistics section
