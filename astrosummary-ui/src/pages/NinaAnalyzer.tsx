import { useState } from 'react'
import ChartCard from '../components/ChartCard'
import { API_URL } from '../lib/apiConfig'

function TotalsBar({totals}:{totals:Record<string, number>}){
  const entries = Object.entries(totals)
  if(entries.length===0) return <div className="text-sm text-text-secondary">No totals</div>
  const max = Math.max(...entries.map(([,v])=>v))
  return (
    <div className="space-y-1">
      {entries.map(([k,v])=> (
        <div key={k} className="flex items-center text-sm">
          <div className="w-36 text-right mr-2">{k}</div>
          <div className="h-4 bg-gray-200 rounded flex-1 mr-2">
            <div style={{width: `${(v/max)*100}%`}} className="h-4 bg-accent-primary rounded" />
          </div>
          <div className="w-24 text-right">{formatSec(v)}</div>
        </div>
      ))}
    </div>
  )
}

function formatSec(s: number){
  if(!isFinite(s) || s<=0) return '0:00'
  // Round to nearest minute and format as H:MM (hours:minutes)
  const totalMinutes = Math.round(s / 60)
  const hrs = Math.floor(totalMinutes / 60)
  const mins = totalMinutes % 60
  return `${String(hrs).padStart(1,'0')}:${String(mins).padStart(2,'0')}`
}

export default function NinaAnalyzer() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedFilters, setSelectedFilters] = useState<Set<string>>(new Set())
  const [selectedHourFilter, setSelectedHourFilter] = useState<string | null>(null)

  async function submit() {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API_URL}/nina/analyze`, { method: 'POST', body: fd })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const json = await res.json()
      setResult(json)
      setSelectedFilters(new Set()) // Reset filters when new results load
      setSelectedHourFilter(null) // Reset hour filter when new results load
    } catch (e: any) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  function toggleFilter(label: string) {
    setSelectedFilters(prev => {
      const next = new Set(prev)
      if (next.has(label)) {
        next.delete(label)
      } else {
        next.add(label)
      }
      return next
    })
  }

  function clearFilters() {
    setSelectedFilters(new Set())
  }

  // Helper to extract hour key from ISO timestamp (e.g., "2024-01-15T21:33:09" -> "2024-01-15 21:00")
  function getHourFromTimestamp(isoTs: string): string {
    const match = isoTs.match(/^(\d{4}-\d{2}-\d{2})T(\d{2})/)
    if (match) {
      return `${match[1]} ${match[2]}:00`
    }
    return ''
  }

  // Filter bursts by selected hour
  const filteredBursts = result?.rms_analysis?.bursts?.filter((b: any) =>
    !selectedHourFilter || getHourFromTimestamp(b.start_ts) === selectedHourFilter
  ) || []

  // Get unique event labels from segments
  const eventLabels = result ? Array.from(new Set<string>(result.segments.map((s: any) => s.label))).sort() : []

  // Filter segments based on selected filters
  const filteredSegments = result?.segments.filter((s: any) =>
    selectedFilters.size === 0 || selectedFilters.has(s.label)
  ) || []

  return (
    <div className="space-y-4">
      <ChartCard title="NINA Session Analyzer">
        <div className="p-4">
          <input type="file" accept="text/*" onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)} />
          <div className="mt-2">
            <button className="px-3 py-2 rounded bg-accent-primary text-black" onClick={submit} disabled={!file || loading}>{loading ? 'Analyzing\u2026' : 'Analyze'}</button>
          </div>
          {error && <div className="mt-2 text-red-400">{error}</div>}
          {result && (
            <div className="mt-4 text-sm text-text-secondary">
              <div className="grid grid-cols-3 gap-4">
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-xs text-gray-500">Productive</div>
                  <div className="text-lg font-semibold">{formatSec(result.productive_seconds)}</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-xs text-gray-500">Idle</div>
                  <div className="text-lg font-semibold">{formatSec(result.idle_seconds)}</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-xs text-gray-500">Lines</div>
                  <div className="text-lg font-semibold">{result.lines_matched}/{result.lines_total} ({result.lines_skipped_ts} skipped)</div>
                </div>
              </div>

              <div className="mt-4">
                <div className="font-semibold mb-2">Totals</div>
                <TotalsBar totals={result.totals_seconds || {}} />
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-semibold">Filter Events</div>
                  {selectedFilters.size > 0 && (
                    <button
                      onClick={clearFilters}
                      className="text-xs px-2 py-1 rounded bg-gray-200 hover:bg-gray-300"
                    >
                      Clear ({selectedFilters.size})
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 mb-3">
                  {eventLabels.map((label: string) => (
                    <label key={label} className="flex items-center gap-1 text-xs cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedFilters.has(label)}
                        onChange={() => toggleFilter(label)}
                        className="cursor-pointer"
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="mt-4">
                <div className="font-semibold">
                  Segments
                  {selectedFilters.size > 0 && ` (filtered: ${filteredSegments.length} of ${result.segments.length})`}
                  {selectedFilters.size === 0 && ` (showing first 50 of ${result.segments.length})`}
                </div>
                <div className="mt-2 overflow-auto max-h-64">
                  <table className="min-w-full text-sm">
                    <thead className="text-left text-xs text-gray-500">
                      <tr><th>start</th><th>end</th><th>label</th><th>dur(h:mm)</th><th>meta</th></tr>
                    </thead>
                    <tbody>
                      {(selectedFilters.size > 0 ? filteredSegments : result.segments.slice(0,50)).map((s:any, idx:number)=> (
                        <tr key={idx} className="border-t">
                          <td className="align-top pr-4">{s.start}</td>
                          <td className="align-top pr-4">{s.end}</td>
                          <td className="align-top pr-4">{s.label}</td>
                          <td className="align-top pr-4">{formatSec(s.duration_seconds)}</td>
                          <td className="align-top pr-4"><pre className="whitespace-pre-wrap">{JSON.stringify(s.meta)}</pre></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* RMS Threshold Analysis Section */}
              {result.rms_analysis && (
                <div className="mt-6 pt-4 border-t border-gray-200">
                  <div className="font-semibold mb-3 text-base">RMS Threshold Analysis</div>

                  {/* Summary Cards */}
                  <div className="grid grid-cols-5 gap-3 mb-4">
                    <div className="p-2 bg-gray-50 rounded">
                      <div className="text-xs text-gray-500">Total Events</div>
                      <div className="text-lg font-semibold">{result.rms_analysis.total_event_count}</div>
                    </div>
                    <div className="p-2 bg-gray-50 rounded">
                      <div className="text-xs text-gray-500">Distinct Bursts</div>
                      <div className="text-lg font-semibold">{result.rms_analysis.total_burst_count}</div>
                    </div>
                    <div className="p-2 bg-gray-50 rounded">
                      <div className="text-xs text-gray-500">Peak RMS</div>
                      <div className="text-lg font-semibold">{result.rms_analysis.max_peak_rms ?? 'N/A'}</div>
                    </div>
                    <div className="p-2 bg-gray-50 rounded">
                      <div className="text-xs text-gray-500">Near Dither</div>
                      <div className="text-lg font-semibold">{result.rms_analysis.correlation?.percent_bursts_near_dither ?? 0}%</div>
                    </div>
                    <div className="p-2 bg-gray-50 rounded">
                      <div className="text-xs text-gray-500">Near Autofocus</div>
                      <div className="text-lg font-semibold">{result.rms_analysis.correlation?.percent_bursts_near_autofocus ?? 0}%</div>
                    </div>
                  </div>

                  {/* Worst Hour Info */}
                  {result.rms_analysis.worst_hour_by_events && (
                    <div className="mb-4 text-sm">
                      <span className="text-gray-500">Worst hour by events: </span>
                      <span className="font-medium">{result.rms_analysis.worst_hour_by_events}</span>
                      {result.rms_analysis.events_per_hour?.[result.rms_analysis.worst_hour_by_events] && (
                        <span className="text-gray-500"> ({result.rms_analysis.events_per_hour[result.rms_analysis.worst_hour_by_events]} events)</span>
                      )}
                    </div>
                  )}

                  {/* Bursts Table */}
                  {result.rms_analysis.bursts && result.rms_analysis.bursts.length > 0 && (
                    <div className="mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-semibold">
                          RMS Bursts
                          {selectedHourFilter
                            ? ` (${filteredBursts.length} of ${result.rms_analysis.bursts.length} in ${selectedHourFilter.split(' ')[1]})`
                            : ` (${result.rms_analysis.bursts.length})`
                          }
                        </div>
                        {selectedHourFilter && (
                          <button
                            onClick={() => setSelectedHourFilter(null)}
                            className="text-xs px-2 py-1 rounded bg-gray-200 hover:bg-gray-300"
                          >
                            Clear hour filter
                          </button>
                        )}
                      </div>
                      <div className="overflow-auto max-h-64">
                        <table className="min-w-full text-sm">
                          <thead className="text-left text-xs text-gray-500">
                            <tr>
                              <th className="pr-2">Start</th>
                              <th className="pr-2">Duration</th>
                              <th className="pr-2">Events</th>
                              <th className="pr-2">Peak RMS</th>
                              <th className="pr-2">Avg RMS</th>
                              <th className="pr-2">Tags</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredBursts.map((b: any, idx: number) => (
                              <tr key={idx} className="border-t">
                                <td className="align-top pr-2">{b.start_ts.replace('T', ' ')}</td>
                                <td className="align-top pr-2">{b.duration_sec.toFixed(1)}s</td>
                                <td className="align-top pr-2">{b.event_count}</td>
                                <td className="align-top pr-2 font-medium">{b.peak_rms.toFixed(2)}</td>
                                <td className="align-top pr-2">{b.avg_rms.toFixed(2)}</td>
                                <td className="align-top pr-2">
                                  {b.tags.map((tag: string) => (
                                    <span key={tag} className="inline-block px-1 py-0.5 mr-1 text-xs bg-blue-100 text-blue-700 rounded">
                                      {tag.replace('near_', '')}
                                    </span>
                                  ))}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Events Per Hour */}
                  {result.rms_analysis.events_per_hour && Object.keys(result.rms_analysis.events_per_hour).length > 0 && (
                    <div className="mt-4">
                      <div className="font-semibold mb-2">Events Per Hour <span className="font-normal text-gray-500">(click to filter bursts)</span></div>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(result.rms_analysis.events_per_hour)
                          .sort(([a], [b]) => a.localeCompare(b))
                          .map(([hour, count]: [string, any]) => (
                            <button
                              key={hour}
                              onClick={() => setSelectedHourFilter(selectedHourFilter === hour ? null : hour)}
                              className={`px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
                                selectedHourFilter === hour
                                  ? 'bg-blue-500 text-white'
                                  : 'bg-gray-100 hover:bg-gray-200'
                              }`}
                            >
                              <span className={selectedHourFilter === hour ? 'text-blue-100' : 'text-gray-500'}>{hour.split(' ')[1]}: </span>
                              <span className="font-medium">{count}</span>
                            </button>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Settings Changes */}
                  {result.rms_analysis.settings_changes && result.rms_analysis.settings_changes.length > 0 && (
                    <div className="mt-4">
                      <div className="font-semibold mb-2">Settings Changes Detected</div>
                      <div className="overflow-auto max-h-40">
                        <table className="min-w-full text-sm">
                          <thead className="text-left text-xs text-gray-500">
                            <tr>
                              <th className="pr-3">Time</th>
                              <th className="pr-3">Setting</th>
                              <th className="pr-3">Value</th>
                              <th className="pr-3">Note</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.rms_analysis.settings_changes.map((sc: any, idx: number) => (
                              <tr key={idx} className="border-t">
                                <td className="align-top pr-3">{sc.ts.replace('T', ' ')}</td>
                                <td className="align-top pr-3">
                                  <span className="px-1 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
                                    {sc.setting_type.replace('_', ' ')}
                                  </span>
                                </td>
                                <td className="align-top pr-3 font-medium">{sc.value}</td>
                                <td className="align-top pr-3 text-gray-500 text-xs">{sc.note || ''}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {result.rms_analysis.total_event_count === 0 && (
                    <div className="text-sm text-gray-500 italic">No RMS threshold events detected in this log.</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </ChartCard>
    </div>
  )
}
