import type { LightFrame } from './types'

// Compute total seconds by target and filter from frames
export function totalsByTarget(frames: LightFrame[]) {
	const out: Record<string, Record<string, number>> = {}
	for (const f of frames) {
		const t = f.target || 'Unknown'
		const filter = f.filter || 'Unknown'
		out[t] = out[t] || {}
		out[t][filter] = (out[t][filter] || 0) + (f.exposure_s || 0)
	}
	return out
}

// When no frames exist, compute an equal goal (equal weights for common filters)
export function computeEqualGoal(_frames: LightFrame[]) {
	// default equal weights for common filters
	return { Ha: 1, OIII: 1, SII: 1, R: 1, G: 1, B: 1, L: 1 }
}
