import { useMemo, useState } from 'react'
import { useApp } from '../context/AppContext'
import { scanFrames } from '../lib/scan'
import type { AstroBinRow } from '../lib/types'
import { DEFAULT_FILTER_MAP_TEXT, parseFilterMap } from '../lib/presets'
import { copyToClipboard, downloadText } from '../lib/utils'

export default function AstroBinExport() {
  const { frames, setFrames, recurse, backendPath } = useApp()
  const [filterMapText, setFilterMapText] = useState(DEFAULT_FILTER_MAP_TEXT)
  const [status, setStatus] = useState('')
  const [scanning, setScanning] = useState(false)

  const onScan = async () => {
    setScanning(true)
    try {
      const { frames: lf, info } = await scanFrames({ backendPath, recurse })
      setFrames(lf)
      setStatus(info)
    } finally {
      setScanning(false)
    }
  }

  const grouped: AstroBinRow[] = useMemo(() => {
    const fmap = parseFilterMap(filterMapText)
    const by: Record<string, AstroBinRow> = {}
    for (const fr of frames) {
      if (fr.frameType !== 'LIGHT' || !fr.exposure_s) continue
      const row: AstroBinRow = {
        date: fr.date,
        filter: fmap[fr.filter] ?? '',
        number: 1,
        duration: fr.exposure_s,
      }
      const k = `${row.date}__${row.filter}__${row.duration}`
      if (!by[k]) by[k] = row
      else by[k].number += 1
    }
    return Object.values(by).sort((a, b) => a.date.localeCompare(b.date))
  }, [frames, filterMapText])

  const csv = useMemo(() => {
    const cols = ['date', 'filter', 'number', 'duration']
    const lines = [cols.join(',')]
    for (const r of grouped) {
      lines.push([r.date, r.filter, r.number, r.duration.toFixed(4)].join(','))
    }
    return lines.join('\n')
  }, [grouped])

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-center">
        <button
          className="px-3 py-2 rounded-xl bg-accent-primary text-black disabled:opacity-60"
          onClick={onScan}
          disabled={scanning}
        >
          {scanning ? 'Scanning…' : 'Scan'}
        </button>
        <button className="px-3 py-2 rounded-xl bg-slate-700" onClick={() => copyToClipboard(csv)}>Copy CSV</button>
        <button className="px-3 py-2 rounded-xl bg-slate-700" onClick={() => downloadText('astrobin_acquisitions.csv', csv)}>Download CSV</button>
      </div>

      {scanning && (
        <div className="mt-1 h-1 bg-slate-700 rounded overflow-hidden">
          <div className="animate-pulse bg-accent-primary h-1 w-full"></div>
        </div>
      )}

      <div className="text-xs text-text-secondary">{status}</div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <div className="text-sm mb-2">Filter → AstroBin ID map</div>
          <textarea
            value={filterMapText}
            onChange={(e) => setFilterMapText(e.target.value)}
            rows={10}
            className="w-full bg-bg-card border border-slate-700 rounded-xl p-3 text-sm"
          />
          <div className="text-xs text-text-secondary mt-2">
            Example: <code>Ha=4657</code>. Unmapped filters export with empty <code>filter</code>.
          </div>
        </div>

        <div>
          <div className="text-sm mb-2">Preview ({grouped.length} rows)</div>
          <div className="bg-bg-card border border-slate-800 rounded-xl overflow-auto max-h-[420px]">
            <table className="w-full text-sm">
              <thead className="bg-slate-800">
                <tr>
                  <th className="text-left p-2">date</th>
                  <th className="text-left p-2">filter</th>
                  <th className="text-left p-2">number</th>
                  <th className="text-left p-2">duration</th>
                </tr>
              </thead>
              <tbody>
                {grouped.map((r, i) => (
                  <tr key={i} className="odd:bg-slate-900/40">
                    <td className="p-2">{r.date}</td>
                    <td className="p-2">{r.filter as any}</td>
                    <td className="p-2">{r.number}</td>
                    <td className="p-2">{r.duration.toFixed(4)}</td>
                  </tr>
                ))}
                {grouped.length === 0 && !scanning && (
                  <tr><td className="p-3 text-text-secondary" colSpan={4}>No rows — click Scan.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-3">
            <div className="text-sm mb-1">CSV (first 10 lines)</div>
            <pre className="bg-slate-900 border border-slate-800 rounded-xl p-3 text-xs overflow-auto max-h-40">
{csv.split('\n').slice(0, 10).join('\n')}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
