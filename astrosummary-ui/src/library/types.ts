// Type definition for LightFrame used in scan and analysis
export type LightFrame = {
	target?: string;
	filter?: string;
	exposure_s?: number;
	[key: string]: any;
};

// Type for AstroBin export rows
export type AstroBinRow = {
	date: string;
	filter: string;
	number: number;
	duration: number;
};

// Type for mode selection
export type Mode = 'AstroBin Export' | 'Target Data Visualizer';
