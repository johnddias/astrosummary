import { useState, useMemo } from 'react'
import ChartCard from '../components/ChartCard'
import CollapsibleSection from '../components/CollapsibleSection'
import { API_URL } from '../lib/apiConfig'
import { useApp } from '../context/AppContext'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

interface BurstChartPoint {
  timestamp: number
  timeLabel: string
  peakRms: number
  avgRms: number
  eventCount: number
  tags: string[]
  type: 'burst'
}

interface StarLostChartPoint {
  timestamp: number
  timeLabel: string
  reason: string
  type: 'star_lost'
  peakRms: number  // Use same field name as bursts so it maps to the Y axis
}

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
  const {
    ninaAnalysis: result,
    setNinaAnalysis: setResult,
    ninaSelectedFilters: selectedFilters,
    setNinaSelectedFilters: setSelectedFilters,
    ninaSelectedHourFilter: selectedHourFilter,
    setNinaSelectedHourFilter: setSelectedHourFilter,
    ninaSelectedTagFilters: selectedTagFilters,
    setNinaSelectedTagFilters: setSelectedTagFilters,
    phd2Analysis,
  } = useApp()
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      setSelectedTagFilters(new Set()) // Reset tag filters when new results load
    } catch (e: any) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  function toggleFilter(label: string) {
    const next = new Set(selectedFilters)
    if (next.has(label)) {
      next.delete(label)
    } else {
      next.add(label)
    }
    setSelectedFilters(next)
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

  function toggleTagFilter(tag: string) {
    const next = new Set(selectedTagFilters)
    if (next.has(tag)) {
      next.delete(tag)
    } else {
      next.add(tag)
    }
    setSelectedTagFilters(next)
  }

  // Get unique tags from all bursts
  const allBurstTags: string[] = result?.rms_analysis?.bursts
    ? Array.from(new Set<string>(
        result.rms_analysis.bursts.flatMap((b: any) => b.tags || [])
      )).sort()
    : []

  // Filter bursts by selected hour and tags
  const filteredBursts = result?.rms_analysis?.bursts?.filter((b: any) => {
    const matchesHour = !selectedHourFilter || getHourFromTimestamp(b.start_ts) === selectedHourFilter
    const matchesTags = selectedTagFilters.size === 0 ||
      Array.from(selectedTagFilters).some(tag => b.tags?.includes(tag))
    return matchesHour && matchesTags
  }) || []

  // Get unique event labels from segments
  const eventLabels = result ? Array.from(new Set<string>(result.segments.map((s: any) => s.label))).sort() : []

  // Filter segments based on selected filters
  const filteredSegments = result?.segments.filter((s: any) =>
    selectedFilters.size === 0 || selectedFilters.has(s.label)
  ) || []

  // Prepare chart data for RMS bursts time series
  const chartData = useMemo((): BurstChartPoint[] => {
    if (!filteredBursts || filteredBursts.length === 0) return []

    // Convert bursts to chart points
    const burstPoints: BurstChartPoint[] = filteredBursts.map((b: any) => {
      const date = new Date(b.start_ts)
      return {
        timestamp: date.getTime(),
        timeLabel: b.start_ts.replace('T', ' ').substring(11, 19),
        peakRms: b.peak_rms,
        avgRms: b.avg_rms,
        eventCount: b.event_count,
        tags: b.tags,
        type: 'burst' as const,
      }
    })

    return burstPoints.sort((a, b) => a.timestamp - b.timestamp)
  }, [filteredBursts])

  // Prepare PHD2 star lost events for chart overlay
  const starLostChartData = useMemo((): StarLostChartPoint[] => {
    if (!phd2Analysis?.star_lost_events || phd2Analysis.star_lost_events.length === 0) return []
    if (chartData.length === 0) return []

    // Get the time range from bursts
    const minBurstTime = chartData[0].timestamp
    const maxBurstTime = chartData[chartData.length - 1].timestamp

    const points: StarLostChartPoint[] = phd2Analysis.star_lost_events
      .map((s: any): StarLostChartPoint => {
        const date = new Date(s.timestamp)
        return {
          timestamp: date.getTime(),
          timeLabel: s.timestamp.replace('T', ' ').substring(11, 19),
          reason: s.reason || 'unknown',
          type: 'star_lost' as const,
          peakRms: 0.15,  // Show near bottom of chart but visible above 0
        }
      })

    points.sort((a, b) => a.timestamp - b.timestamp)

    // Filter to events within the burst time range (with 2 hour buffer on each side)
    const buffer = 2 * 3600000 // 2 hours in ms
    const filtered = points.filter((s) =>
      s.timestamp >= minBurstTime - buffer && s.timestamp <= maxBurstTime + buffer
    )

    // If no events match the time range, return empty (logs from different sessions)
    return filtered
  }, [phd2Analysis, chartData])

  // Count of star lost events that didn't match the time range (for info display)
  const unmatchedStarLostCount = useMemo(() => {
    if (!phd2Analysis?.star_lost_events) return 0
    return phd2Analysis.star_lost_events.length - starLostChartData.length
  }, [phd2Analysis, starLostChartData])

  // Custom tooltip for the chart
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || payload.length === 0) return null
    const data = payload[0].payload
    if (data.type === 'burst') {
      return (
        <div className="bg-slate-800 border border-slate-600 rounded p-2 text-xs">
          <div className="text-text-primary font-medium">{data.timeLabel}</div>
          <div className="text-yellow-400">Peak RMS: {data.peakRms.toFixed(2)}</div>
          <div className="text-blue-400">Avg RMS: {data.avgRms.toFixed(2)}</div>
          <div className="text-text-secondary">Events: {data.eventCount}</div>
          {data.tags?.length > 0 && (
            <div className="text-purple-400">Tags: {data.tags.join(', ')}</div>
          )}
        </div>
      )
    } else if (data.type === 'star_lost') {
      return (
        <div className="bg-slate-800 border border-slate-600 rounded p-2 text-xs">
          <div className="text-text-primary font-medium">{data.timeLabel}</div>
          <div className="text-orange-400">Star Lost: {data.reason}</div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-4">
      <ChartCard title="NINA Session Analyzer">
        <div className="p-4">
          <input type="file" accept="text/*" onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)} />
          <div className="mt-2">
            <button className="px-3 py-2 rounded bg-accent-primary text-black" onClick={submit} disabled={!file || loading}>{loading ? 'Analyzing\u2026' : 'Analyze'}</button>
          </div>
          {result?.original_filename && (
            <div className="mt-2 text-xs text-text-secondary">
              Last analyzed: <span className="font-medium">{result.original_filename}</span>
            </div>
          )}
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
                <CollapsibleSection
                  title={
                    <span>
                      Segments
                      {selectedFilters.size > 0 && ` (filtered: ${filteredSegments.length} of ${result.segments.length})`}
                      {selectedFilters.size === 0 && ` (${result.segments.length} total)`}
                    </span>
                  }
                >
                  <div className="overflow-auto max-h-64">
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
                </CollapsibleSection>
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

                  {/* RMS Bursts Time Series Chart */}
                  {chartData.length > 0 && (
                    <div className="mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-semibold text-text-primary">
                          RMS Bursts Timeline
                          {(selectedHourFilter || selectedTagFilters.size > 0)
                            ? ` (${filteredBursts.length} filtered)`
                            : ` (${result.rms_analysis.bursts?.length || 0} total)`
                          }
                          {starLostChartData.length > 0 && (
                            <span className="ml-2 text-orange-400 font-normal text-xs">
                              + {starLostChartData.length} star lost events from PHD2
                            </span>
                          )}
                          {starLostChartData.length === 0 && unmatchedStarLostCount > 0 && (
                            <span className="ml-2 text-text-secondary font-normal text-xs">
                              (PHD2 has {unmatchedStarLostCount} star lost events from different session)
                            </span>
                          )}
                        </div>
                        {(selectedHourFilter || selectedTagFilters.size > 0) && (
                          <button
                            onClick={() => { setSelectedHourFilter(null); setSelectedTagFilters(new Set()) }}
                            className="text-xs px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-text-secondary"
                          >
                            Clear filters
                          </button>
                        )}
                      </div>

                      {/* Tag filters */}
                      {allBurstTags.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-3">
                          <span className="text-xs text-text-secondary self-center">Filter by tag:</span>
                          {allBurstTags.map((tag: string) => (
                            <button
                              key={tag}
                              onClick={() => toggleTagFilter(tag)}
                              className={`px-2 py-0.5 rounded text-xs cursor-pointer transition-colors ${
                                selectedTagFilters.has(tag)
                                  ? 'bg-blue-500 text-white'
                                  : 'bg-slate-700 text-text-secondary hover:bg-slate-600'
                              }`}
                            >
                              {tag.replace('near_', '')}
                            </button>
                          ))}
                        </div>
                      )}

                      <div className="h-64 bg-slate-900 rounded p-2">
                        <ResponsiveContainer width="100%" height="100%">
                          <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 40 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                            <XAxis
                              dataKey="timestamp"
                              type="number"
                              domain={['dataMin', 'dataMax']}
                              tickFormatter={(ts) => {
                                const d = new Date(ts)
                                return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
                              }}
                              stroke="#9CA3AF"
                              fontSize={10}
                            />
                            <YAxis
                              dataKey="peakRms"
                              name="Peak RMS"
                              stroke="#9CA3AF"
                              fontSize={10}
                              domain={[0, 'auto']}
                              label={{ value: 'Peak RMS', angle: -90, position: 'insideLeft', fill: '#9CA3AF', fontSize: 10 }}
                            />
                            <Tooltip content={<CustomTooltip />} />
                            <ReferenceLine y={1.5} stroke="#EF4444" strokeDasharray="5 5" label={{ value: '1.5 threshold', fill: '#EF4444', fontSize: 10, position: 'right' }} />
                            {/* RMS Burst points */}
                            <Scatter
                              name="RMS Bursts"
                              data={chartData}
                              fill="#FBBF24"
                              shape="circle"
                            />
                            {/* Star Lost events as triangles at y=0 */}
                            {starLostChartData.length > 0 && (
                              <Scatter
                                name="Star Lost"
                                data={starLostChartData}
                                fill="#F97316"
                                shape="triangle"
                                yAxisId={0}
                              />
                            )}
                          </ScatterChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="flex gap-4 mt-2 text-xs text-text-secondary">
                        <div className="flex items-center gap-1">
                          <span className="w-3 h-3 rounded-full bg-yellow-400"></span>
                          <span>RMS Burst</span>
                        </div>
                        {starLostChartData.length > 0 && (
                          <div className="flex items-center gap-1">
                            <span className="w-0 h-0 border-l-[6px] border-r-[6px] border-b-[10px] border-l-transparent border-r-transparent border-b-orange-500"></span>
                            <span>Star Lost (PHD2)</span>
                          </div>
                        )}
                        <div className="flex items-center gap-1">
                          <span className="w-6 h-0 border-t-2 border-dashed border-red-500"></span>
                          <span>1.5" threshold</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Bursts Table */}
                  {result.rms_analysis.bursts && result.rms_analysis.bursts.length > 0 && (
                    <div className="mt-4">
                      <CollapsibleSection
                        title={
                          <span>
                            RMS Bursts Table
                            {(selectedHourFilter || selectedTagFilters.size > 0)
                              ? ` (${filteredBursts.length} of ${result.rms_analysis.bursts.length} filtered)`
                              : ` (${result.rms_analysis.bursts.length})`
                            }
                          </span>
                        }
                      >
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
                      </CollapsibleSection>
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
                      <CollapsibleSection
                        title={`Settings Changes Detected (${result.rms_analysis.settings_changes.length})`}
                      >
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
                      </CollapsibleSection>
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
