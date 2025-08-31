import type { LightFrame } from './types';

export async function scanFrames({ backendPath, recurse }: { backendPath: string; recurse: boolean }): Promise<{ frames: LightFrame[]; info?: any }> {
	// Call backend /scan API
	try {
		const res = await fetch('http://127.0.0.1:8000/scan', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ path: backendPath, recurse, extensions: ['.fit', '.fits'] })
		});
		if (!res.ok) throw new Error('Scan failed');
		const data = await res.json();
		return { frames: data.frames || [], info: `Scanned ${data.files_scanned} files, matched ${data.files_matched}` };
	} catch (err) {
		return { frames: [], info: 'Scan failed' };
	}
}
