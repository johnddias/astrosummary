import type { LightFrame, RejectionData } from './types';
import { API_URL } from '../lib/apiConfig';

export type ScanProgress = { files_scanned: number; files_matched: number; total_files?: number }

// scanFrames supports incremental progress via onProgress callback.
export async function scanFrames({ backendPath, recurse }: { backendPath: string; recurse: boolean }, onProgress?: (p: ScanProgress) => void, onFrame?: (f: LightFrame) => void): Promise<{ frames: LightFrame[]; info?: any; rejectionData?: RejectionData }> {
	const frames: LightFrame[] = []
	let rejectionData: RejectionData | undefined = undefined
	
	try {
		const res = await fetch(`${API_URL}/scan_stream`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ path: backendPath, recurse, extensions: ['.fit', '.fits'] })
		})
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
	} catch {
		return { frames: [], info: 'Scan failed' }
	}
}
