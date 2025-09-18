// Type definition for LightFrame used in scan and analysis
export type LightFrame = {
	target: string;
	filter: string;
	exposure_s: number;
	date: string;
	frameType: 'LIGHT' | 'DARK' | 'FLAT' | 'BIAS' | 'OTHER';
	file_path?: string;
	rejected?: boolean;
	[key: string]: any;
};

// Type for rejection data from ProcessLogger.txt
export interface RejectionData {
	rejected_frames: string[];
	quality_data: Record<string, any>;
	rejection_logs: string[];
	rejected_count: number;
}

// Type for scan response including rejection data
export interface ScanResponse {
	frames: LightFrame[];
	files_scanned: number;
	files_matched: number;
	rejection_data?: RejectionData;
}

// Type for AstroBin export rows
export type AstroBinRow = {
	date: string;
	filter: string;
	number: number;
	duration: number;
};

// Type for mode selection
export type Mode = 'Ratio Planner' | 'AstroBin Export' | 'Target Data Visualizer' | 'NINA Analyzer';
