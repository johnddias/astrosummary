import { useMemo, useState } from 'react'
import { useApp } from '../context/AppContext'
import type { AstroBinRow } from '../library/types'
import { DEFAULT_FILTER_MAP_TEXT, parseFilterMap } from '../library/presets'
import { copyToClipboard, downloadText } from '../library/utils'

export default function AstroBinExport() {
  const { frames } = useApp()
  const [filterMapText, setFilterMapText] = useState(DEFAULT_FILTER_MAP_TEXT)
  const [copiedTargets, setCopiedTargets] = useState<Record<string, boolean>>({})
  const [copyErrors, setCopyErrors] = useState<Record<string, string>>({})
  const [collapsedTargets, setCollapsedTargets] = useState<Record<string, boolean>>({})
  const [showCsvExample, setShowCsvExample] = useState(false)
  const [showMap, setShowMap] = useState(false)

  // scanning is handled by `onScan` from context (Sidebar provides the Scan button)

  const groupedByTarget: Record<string, AstroBinRow[]> = useMemo(() => {
    const fmap = parseFilterMap(filterMapText)
    const out: Record<string, Record<string, AstroBinRow>> = {}
    for (const fr of frames) {
      // Only include LIGHT frames (server also filters, but double-check here)
      if (fr.frameType !== 'LIGHT' || !fr.exposure_s) continue
      const filterId = fmap[fr.filter?.toLowerCase?.() ?? fr.filter] ?? ''
      const row: AstroBinRow = {
        date: fr.date,
        filter: filterId,
        number: 1,
        duration: fr.exposure_s,
      }
      const target = fr.target || 'Unknown'
      const key = `${row.date}__${row.filter}__${row.duration}`
      out[target] = out[target] || {}
      if (!out[target][key]) out[target][key] = row
      else out[target][key].number += 1
    }
    // Convert grouped maps to sorted arrays
    const final: Record<string, AstroBinRow[]> = {}
    for (const t of Object.keys(out).sort((a, b) => a.localeCompare(b))) {
      final[t] = Object.values(out[t]).sort((a, b) => a.date.localeCompare(b.date))
    }
    return final
  }, [frames, filterMapText])

  const csv = useMemo(() => {
    const cols = ['target', 'date', 'filter', 'number', 'duration']
    const lines = [cols.join(',')]
    for (const [target, rows] of Object.entries(groupedByTarget)) {
      for (const r of rows) {
        lines.push([target, r.date, r.filter, r.number, r.duration.toFixed(4)].join(','))
      }
    }
    return lines.join('\n')
  }, [groupedByTarget])

  return (
    <div className="space-y-4">

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm">Filter → AstroBin ID map</div>
            <button
              className="px-2 py-1 rounded bg-slate-700 text-sm"
              onClick={() => setShowMap((v) => !v)}
            >
              {showMap ? 'Hide Filter Map' : 'View Filter Map'}
            </button>
          </div>

          {showMap ? (
            <>
              <textarea
                value={filterMapText}
                onChange={(e) => setFilterMapText(e.target.value)}
                rows={10}
                className="w-full bg-bg-card border border-slate-700 rounded-xl p-3 text-sm"
              />
              <div className="text-xs text-text-secondary mt-2">
                Example: <code>Ha=4657</code>. Unmapped filters export with empty <code>filter</code>.
                Matching is case-insensitive.
              </div>
            </>
          ) : (
            <div className="text-xs text-text-secondary p-3 bg-bg-card border border-slate-700 rounded-xl">
              Filter map hidden. Click "View Filter Map" to view or edit mappings.
            </div>
          )}
        </div>
      </div>

      <section className="mt-6">
        <div className="text-sm mb-2">Preview ({Object.values(groupedByTarget).reduce((s, arr) => s + arr.length, 0)} rows)</div>
        <div className="space-y-6">
          {Object.keys(groupedByTarget).length === 0 && (
            <div className="text-text-secondary">No rows — run Scan from the sidebar.</div>
          )}

          {/* Layout: two columns for multiple targets, center single table */}
          <div className={Object.keys(groupedByTarget).length === 1 ? 'flex justify-center' : 'grid grid-cols-1 md:grid-cols-2 gap-6'}>
            {Object.entries(groupedByTarget).map(([target, rows]) => {
              const csvForTarget = (() => {
                const cols = ['target', 'date', 'filter', 'number', 'duration']
                const lines = [cols.join(',')]
                for (const r of rows) lines.push([target, r.date, r.filter, r.number, r.duration.toFixed(4)].join(','))
                return lines.join('\n')
              })()

              const onCopy = async () => {
                try {
                  await copyToClipboard(csvForTarget)
                  setCopyErrors((s) => ({ ...s, [target]: '' }))
                  setCopiedTargets((s) => ({ ...s, [target]: true }))
                  setTimeout(() => setCopiedTargets((s) => ({ ...s, [target]: false })), 2000)
                } catch (err) {
                  setCopyErrors((s) => ({ ...s, [target]: 'Failed to copy' }))
                  setTimeout(() => setCopyErrors((s) => ({ ...s, [target]: '' })), 2000)
                }
              }

              const onDownload = () => {
                const safe = target.replace(/[^a-z0-9-_]/gi, '_') || 'target'
                downloadText(`astrobin_${safe}.csv`, csvForTarget)
              }

              return (
                <div key={target} className={Object.keys(groupedByTarget).length === 1 ? 'w-full md:w-2/3' : ''}>
                  <div className="bg-bg-card border border-slate-800 rounded-xl overflow-auto">
                    <div className="p-3 border-b border-slate-800 text-sm font-medium flex items-center justify-between">
                      <div>Target: {target} ({rows.length} rows)</div>
                        <div className="flex items-center gap-2">
                          <button className="px-3 py-1 rounded-xl bg-slate-700 text-sm" onClick={onCopy}>Copy CSV</button>
                          <button className="px-3 py-1 rounded-xl bg-slate-700 text-sm" onClick={onDownload}>Download CSV</button>
                          <button
                            className="px-2 py-1 rounded bg-slate-600 text-xs"
                            onClick={() => setCollapsedTargets((s) => ({ ...s, [target]: !s[target] }))}
                          >
                            {collapsedTargets[target] ? 'Expand' : 'Collapse'}
                          </button>
                          {copiedTargets[target] && (
                            <span className="ml-2 px-3 py-1 rounded-full bg-emerald-600 text-white text-xs">Copied</span>
                          )}
                          {copyErrors[target] && (
                            <span className="ml-2 px-3 py-1 rounded-full bg-red-600 text-white text-xs">{copyErrors[target]}</span>
                          )}
                        </div>
                    </div>
                    {!collapsedTargets[target] && (
                      <div className="max-h-60 overflow-auto">
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
                            {rows.map((r, i) => (
                                <tr key={i} className="odd:bg-slate-900/40">
                                  <td className="p-2">{r.date}</td>
                                  <td className="p-2">{r.filter as any}</td>
                                  <td className="p-2">{r.number}</td>
                                  <td className="p-2">{r.duration.toFixed(4)}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                        <div className="p-2 text-xs text-text-secondary">Showing {rows.length} rows</div>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="mt-3">
          <div className="flex items-center justify-between mb-1">
            <div className="text-sm">CSV layout example</div>
            <button
              className="px-2 py-1 rounded bg-slate-700 text-sm"
              onClick={() => setShowCsvExample((v) => !v)}
            >
              {showCsvExample ? 'Hide' : 'Show'}
            </button>
          </div>

          {showCsvExample ? (
            <pre className="bg-slate-900 border border-slate-800 rounded-xl p-3 text-xs overflow-auto max-h-40">
{csv.split('\n').slice(0, 10).join('\n')}
            </pre>
          ) : (
            <div className="text-xs text-text-secondary p-3 bg-bg-card border border-slate-800 rounded-xl">
              CSV example collapsed. Click "Show" to view the first 10 lines.
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
