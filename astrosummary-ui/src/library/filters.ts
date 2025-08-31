export function normalizeFilter(name: string) {
	if (!name) return 'Unknown'
	const raw = String(name).trim()
	if (!raw) return 'Unknown'
	const lower = raw.toLowerCase()
	// normalize Greek alpha (Hα) to ascii
	const alphaNormalized = lower.replace(/α/g, 'a')
	// remove non-alphanumerics to form a compact token for matching
	const token = alphaNormalized.replace(/[^a-z0-9]/g, '')

	// Hydrogen-alpha variants
	if (token === 'ha' || token === 'halpha' || lower.includes('hydrogen') || /^h\s*a$/.test(lower)) return 'Ha'

	// Oxygen III variants (OIII, O3, o-iii, oxygen iii)
	if (token === 'oiii' || token === 'o3' || token === 'o-iii' || token.includes('oiii') || token.includes('o3') || lower.includes('oxygen')) return 'OIII'

	// Sulfur II variants (SII, S2, s-ii, sulfur ii)
	if (token === 'sii' || token === 's2' || token === 's-ii' || token.includes('sii') || token.includes('s2') || lower.includes('sulfur')) return 'SII'

	// Luminance / L
	if (token === 'l' || token === 'lum' || token === 'luminance' || lower.includes('luminance')) return 'L'

	// Broadband RGB
	if (token === 'r' || lower.includes('red')) return 'R'
	if (token === 'g' || lower.includes('green')) return 'G'
	if (token === 'b' || lower.includes('blue')) return 'B'

	// fallback to original (preserve casing if already a canonical name)
	return raw
}
