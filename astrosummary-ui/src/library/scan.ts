import type { LightFrame, RejectionData } from './types';
import { API_URL } from '../lib/apiConfig';

export type ScanProgress = { files_scanned: number; files_matched: number; total_files?: number }

// scanFrames supports incremental progress via onProgress callback.
export async function scanFrames({ backendPath, recurse }: { backendPath: string; recurse: boolean }, onProgress?: (p: ScanProgress) => void, onFrame?: (f: LightFrame) => void): Promise<{ frames: LightFrame[]; info?: any; rejectionData?: RejectionData }> {
	const frames: LightFrame[] = []
	let rejectionData: RejectionData | undefined = undefined

	try {
		const scanUrl = `${API_URL}/scan_stream`;
		const requestBody = { path: backendPath, recurse, extensions: ['.fit', '.fits'] };

		console.log('=== Scan Request Debug ===');
		console.log('API_URL:', API_URL);
		console.log('Full scan URL:', scanUrl);
		console.log('Request body:', requestBody);
		console.log('========================');

		const res = await fetch(scanUrl, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(requestBody)
		})

		console.log('=== Scan Response Debug ===');
		console.log('Response status:', res.status);
		console.log('Response ok:', res.ok);
		console.log('Response headers:', Object.fromEntries(res.headers.entries()));
		console.log('==========================');

		if (!res.ok || !res.body) throw new Error('Scan failed')

		const reader = res.body.getReader()
		const decoder = new TextDecoder('utf-8')
		let buf = ''
		while (true) {
			const { done, value } = await reader.read()
			if (done) break
			buf += decoder.decode(value, { stream: true })
			let idx
			while ((idx = buf.indexOf('\n')) >= 0) {
				const line = buf.slice(0, idx).trim()
				buf = buf.slice(idx + 1)
				if (!line) continue
				try {
					const obj = JSON.parse(line)
					
					if (obj.type === 'progress') {
						onProgress?.({ files_scanned: obj.files_scanned, files_matched: obj.files_matched, total_files: obj.total_files })
					} else if (obj.type === 'frame') {
						// notify caller immediately about the new frame
						try { onFrame?.(obj.frame) } catch {}
						frames.push(obj.frame)
						onProgress?.({ files_scanned: obj.files_scanned ?? 0, files_matched: obj.files_matched ?? frames.length, total_files: obj.total_files })
					} else if (obj.type === 'done') {
						// Check if rejection data was provided
						if (obj.rejection_data) {
							rejectionData = obj.rejection_data
						}
						console.log('DEBUG scan: final rejectionData:', rejectionData)
						return { frames, info: `Scanned ${obj.files_scanned} files, matched ${obj.files_matched}`, rejectionData }
					}
				} catch (e) {
					// ignore parse errors for now
				}
			}
		}
		return { frames, info: `Scanned ${frames.length} frames`, rejectionData }
	} catch (error) {
		console.error('=== Scan Error Debug ===');
		console.error('Error details:', error);
		console.error('Error message:', error instanceof Error ? error.message : String(error));
		console.error('=======================');
		return { frames: [], info: 'Scan failed' }
	}
}
