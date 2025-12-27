export interface LightFrame {
  target: string;
  filter: string;
  exposure_s: number;
  date: string;
  frameType: 'LIGHT' | 'DARK' | 'FLAT' | 'BIAS' | 'OTHER';
  file_path?: string;
  rejected?: boolean;
}

export interface RejectionData {
  rejected_frames: string[];
  quality_data: Record<string, any>;
  rejection_logs: string[];
  rejected_count: number;
}

export interface ScanResponse {
  frames: LightFrame[];
  files_scanned: number;
  files_matched: number;
  rejection_data?: RejectionData;
}

export interface QualityMetrics {
  snr: number;
  fwhm: number;
  eccentricity: number;
  star_count: number;
  background_median: number;
  background_std: number;
  gradient_strength: number;
  quality_score: number;
  phd2_rms?: number;
}

export interface ValidationResult {
  file_path: string;
  filename: string;
  target: string;
  filter: string;
  date: string;
  rejected_by_wbpp: boolean;
  metrics: QualityMetrics;
  validation_status: 'CORRECT_REJECT' | 'CORRECT_ACCEPT' | 'FALSE_POSITIVE' | 'FALSE_NEGATIVE';
}

export interface ValidationResponse {
  results: ValidationResult[];
  summary: {
    total_frames: number;
    correct_rejects: number;
    correct_accepts: number;
    false_positives: number;
    false_negatives: number;
    accuracy: number;
    wbpp_reject_rate: number;
    mean_quality_rejected: number;
    mean_quality_accepted: number;
  };
}