
// parse lines like `Ha=4657` into a map { 'ha': '4657' }
export function parseFilterMap(text: string) {
	const out: Record<string, string> = {}
	if (!text) return out
	for (const line of text.split(/\r?\n/)) {
		const t = line.trim()
		if (!t) continue
		const parts = t.split('=')
		if (parts.length !== 2) continue
		out[parts[0].trim().toLowerCase()] = parts[1].trim()
	}
	return out
}
export const PRESETS: Record<string, Record<string, number>> = {
	'SHO (equal)': { SII: 1, Ha: 1, OIII: 1 },
	'HOO (Ha-heavy)': { Ha: 2, OIII: 1 },
	'LRGB (equal)': { L: 1, R: 1, G: 1, B: 1 },
}

export const DEFAULT_FILTER_MAP_TEXT = [
	'R=3007',
	'Ha=4657',
	'OIII=4746',
	'SII=4838',
	'L=3012',
	'G=3011',
	'B=3008',
].join('\n')
