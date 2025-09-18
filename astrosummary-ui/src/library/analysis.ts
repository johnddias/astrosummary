import type { LightFrame } from './types'

// Filter out rejected frames if rejection filtering is enabled
export function filterAcceptedFrames(frames: LightFrame[], applyRejectionFilter: boolean = false): LightFrame[] {
	if (!applyRejectionFilter) {
		return frames
	}
	return frames.filter(frame => !frame.rejected)
}

// Compute total seconds by target and filter from frames
export function totalsByTarget(frames: LightFrame[], applyRejectionFilter: boolean = false) {
	const filteredFrames = filterAcceptedFrames(frames, applyRejectionFilter)
	const out: Record<string, Record<string, number>> = {}
	for (const f of filteredFrames) {
		const t = f.target || 'Unknown'
		const filter = f.filter || 'Unknown'
		out[t] = out[t] || {}
		out[t][filter] = (out[t][filter] || 0) + (f.exposure_s || 0)
	}
	return out
}

// Get rejection statistics
export function getRejectionStats(frames: LightFrame[]) {
	const totalFrames = frames.length
	const rejectedFrames = frames.filter(f => f.rejected === true).length
	const acceptedFrames = totalFrames - rejectedFrames
	const rejectionRate = totalFrames > 0 ? rejectedFrames / totalFrames : 0
	
	return {
		totalFrames,
		rejectedFrames,
		acceptedFrames,
		rejectionRate
	}
}

// When no frames exist, compute an equal goal (equal weights for common filters)
export function computeEqualGoal(_frames: LightFrame[]) {
	// default equal weights for common filters
	return { Ha: 1, OIII: 1, SII: 1, R: 1, G: 1, B: 1, L: 1 }
}
