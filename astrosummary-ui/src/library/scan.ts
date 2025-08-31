import type { LightFrame } from './types';

export type ScanProgress = { files_scanned: number; files_matched: number }

// scanFrames supports incremental progress via onProgress callback.
export async function scanFrames({ backendPath, recurse }: { backendPath: string; recurse: boolean }, onProgress?: (p: ScanProgress) => void, onFrame?: (f: LightFrame) => void): Promise<{ frames: LightFrame[]; info?: any }> {
	const frames: LightFrame[] = []
	try {
		const res = await fetch('http://127.0.0.1:8000/scan_stream', {
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
									onProgress?.({ files_scanned: obj.files_scanned, files_matched: obj.files_matched })
								} else if (obj.type === 'frame') {
									// notify caller immediately about the new frame
									try { onFrame?.(obj.frame) } catch {}
									frames.push(obj.frame)
									onProgress?.({ files_scanned: obj.files_scanned ?? 0, files_matched: obj.files_matched ?? frames.length })
								} else if (obj.type === 'done') {
									return { frames, info: `Scanned ${obj.files_scanned} files, matched ${obj.files_matched}` }
								}
				} catch (e) {
					// ignore parse errors for now
				}
			}
		}
		return { frames, info: `Scanned ${frames.length} frames` }
	} catch (err) {
		return { frames: [], info: 'Scan failed' }
	}
}
