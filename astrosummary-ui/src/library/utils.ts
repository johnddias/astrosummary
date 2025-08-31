export async function copyToClipboard(text: string) {
	if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
		return navigator.clipboard.writeText(text)
	}
	// fallback for older browsers
	const ta = document.createElement('textarea')
	ta.value = text
	document.body.appendChild(ta)
	ta.select()
	try { document.execCommand('copy') } finally { document.body.removeChild(ta) }
}

export function downloadText(filename: string, text: string) {
	const blob = new Blob([text], { type: 'text/csv;charset=utf-8;' })
	const url = URL.createObjectURL(blob)
	const a = document.createElement('a')
	a.href = url
	a.download = filename
	document.body.appendChild(a)
	a.click()
	a.remove()
	URL.revokeObjectURL(url)
}
