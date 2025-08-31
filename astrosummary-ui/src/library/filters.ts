export function normalizeFilter(name: string) {
	if (!name) return name
	const s = name.toLowerCase()
	if (s.includes('ha')) return 'Ha'
	if (s.includes('oiii') || s.includes('o3') || s.includes('o-iii')) return 'OIII'
	if (s.includes('sii') || s.includes('s-ii')) return 'SII'
	if (s === 'l' || s === 'lum' || s.includes('luminance')) return 'L'
	if (s === 'r' || s.includes('red')) return 'R'
	if (s === 'g' || s.includes('green')) return 'G'
	if (s === 'b' || s.includes('blue')) return 'B'
	return name
}
