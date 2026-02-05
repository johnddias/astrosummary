import { useState, useMemo } from 'react'
import ChartCard from '../components/ChartCard'
import CollapsibleSection from '../components/CollapsibleSection'
import { API_URL } from '../lib/apiConfig'
import { useApp } from '../context/AppContext'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  Area, ComposedChart, Bar
} from 'recharts'

interface UploadedFile {
  file: File
  type: 'nina_log' | 'phd2_debug' | 'acquisition_details' | 'image_metadata' | 'weather_data'
}

function formatDuration(hours: number): string {
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return `${h}h ${m}m`
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || !isFinite(value)) return 'N/A'
  return `${value.toFixed(1)}%`
}

function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null || !isFinite(value)) return 'N/A'
  return value.toFixed(decimals)
}

export default function SessionAnalyzer() {
  const { sessionAnalysis: result, setSessionAnalysis: setResult } = useApp()
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleFileChange(type: UploadedFile['type'], file: File | null) {
    if (file) {
      setFiles(prev => [...prev.filter(f => f.type !== type), { file, type }])
    } else {
      setFiles(prev => prev.filter(f => f.type !== type))
    }
  }

  async function submit() {
    if (files.length === 0) {
      setError('Please select at least one file')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const fd = new FormData()

      for (const { file, type } of files) {
        switch (type) {
          case 'nina_log':
            fd.append('nina_log', file)
            break
          case 'phd2_debug':
            fd.append('phd2_debug_log', file)
            break
          case 'acquisition_details':
            fd.append('acquisition_details', file)
            break
          case 'image_metadata':
            fd.append('image_metadata', file)
            break
          case 'weather_data':
            fd.append('weather_data', file)
            break
        }
      }

      const res = await fetch(`${API_URL}/session/analyze_upload`, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Server returned ${res.status}: ${text}`)
      }
      const json = await res.json()
      if (!json.success && json.error) {
        throw new Error(json.error)
      }
      setResult(json)
    } catch (e: any) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  function clearResults() {
    setResult(null)
    setFiles([])
  }

  // Prepare HFR timeline data
  const hfrTimelineData = useMemo(() => {
    if (!result?.hfr_timeline) return []
    return result.hfr_timeline.map((pt: any) => ({
      ...pt,
      time: new Date(pt.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
    }))
  }, [result])

  // Prepare weather timeline data
  const weatherTimelineData = useMemo(() => {
    if (!result?.weather_timeline) return []
    return result.weather_timeline.map((pt: any) => ({
      ...pt,
      time: new Date(pt.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
    }))
  }, [result])

  // Prepare guiding timeline data
  const guidingTimelineData = useMemo(() => {
    if (!result?.guiding_timeline) return []
    return result.guiding_timeline.map((pt: any) => ({
      ...pt,
      time: new Date(pt.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
    }))
  }, [result])

  // Prepare focus timeline data
  const focusTimelineData = useMemo(() => {
    if (!result?.focus_timeline) return []
    return result.focus_timeline.map((pt: any) => ({
      ...pt,
      time: new Date(pt.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
    }))
  }, [result])

  const summary = result?.summary

  return (
    <div className="space-y-4">
      {/* File Upload Section */}
      <ChartCard title="Session Analyzer - Unified Analysis">
        <div className="p-4">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">NINA Log</label>
              <input
                type="file"
                accept="text/*"
                onChange={(e) => handleFileChange('nina_log', e.target.files?.[0] || null)}
                className="text-sm"
              />
              {files.find(f => f.type === 'nina_log') && (
                <span className="ml-2 text-xs text-green-400">Selected</span>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">PHD2 Debug Log</label>
              <input
                type="file"
                accept="text/*"
                onChange={(e) => handleFileChange('phd2_debug', e.target.files?.[0] || null)}
                className="text-sm"
              />
              {files.find(f => f.type === 'phd2_debug') && (
                <span className="ml-2 text-xs text-green-400">Selected</span>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Acquisition Details (JSON/CSV)</label>
              <input
                type="file"
                accept=".json,.csv"
                onChange={(e) => handleFileChange('acquisition_details', e.target.files?.[0] || null)}
                className="text-sm"
              />
              {files.find(f => f.type === 'acquisition_details') && (
                <span className="ml-2 text-xs text-green-400">Selected</span>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Image Metadata (JSON/CSV)</label>
              <input
                type="file"
                accept=".json,.csv"
                onChange={(e) => handleFileChange('image_metadata', e.target.files?.[0] || null)}
                className="text-sm"
              />
              {files.find(f => f.type === 'image_metadata') && (
                <span className="ml-2 text-xs text-green-400">Selected</span>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Weather Data (JSON/CSV)</label>
              <input
                type="file"
                accept=".json,.csv"
                onChange={(e) => handleFileChange('weather_data', e.target.files?.[0] || null)}
                className="text-sm"
              />
              {files.find(f => f.type === 'weather_data') && (
                <span className="ml-2 text-xs text-green-400">Selected</span>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            <button
              className="px-4 py-2 rounded bg-accent-primary text-black font-medium disabled:opacity-50"
              onClick={submit}
              disabled={files.length === 0 || loading}
            >
              {loading ? 'Analyzing...' : 'Analyze Session'}
            </button>
            {result && (
              <button
                className="px-4 py-2 rounded bg-slate-700 text-text-secondary hover:bg-slate-600"
                onClick={clearResults}
              >
                Clear
              </button>
            )}
          </div>

          {error && <div className="mt-3 text-red-400 text-sm">{error}</div>}

          {files.length > 0 && (
            <div className="mt-3 text-xs text-text-secondary">
              {files.length} file(s) selected: {files.map(f => f.type.replace('_', ' ')).join(', ')}
            </div>
          )}
        </div>
      </ChartCard>

      {/* Session Summary */}
      {summary && (
        <ChartCard title={`Session Summary - ${summary.target_name}`}>
          <div className="p-4">
            <div className="grid grid-cols-4 gap-4 mb-4">
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Date</div>
                <div className="text-lg font-semibold text-text-primary">{summary.session_date}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Duration</div>
                <div className="text-lg font-semibold text-text-primary">{formatDuration(summary.session_duration_hours)}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Total Frames</div>
                <div className="text-lg font-semibold text-text-primary">{summary.total_frames}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Avg HFR</div>
                <div className="text-lg font-semibold text-text-primary">{formatNumber(summary.avg_hfr)}</div>
              </div>
            </div>

            <div className="grid grid-cols-5 gap-4 mb-4">
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Min HFR</div>
                <div className="text-lg font-semibold text-green-400">{formatNumber(summary.min_hfr)}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Max HFR</div>
                <div className="text-lg font-semibold text-red-400">{formatNumber(summary.max_hfr)}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Avg Stars</div>
                <div className="text-lg font-semibold text-text-primary">{formatNumber(summary.avg_star_count, 0)}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Avg Guiding RMS</div>
                <div className="text-lg font-semibold text-text-primary">{formatNumber(summary.avg_guiding_rms_arcsec)}"</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">PHD2 Settle Rate</div>
                <div className="text-lg font-semibold text-text-primary">{formatPercent(summary.phd2_settle_success_rate)}</div>
              </div>
            </div>

            {/* Filter breakdown */}
            {summary.frames_by_filter && Object.keys(summary.frames_by_filter).length > 0 && (
              <div className="mb-4">
                <div className="text-sm font-medium text-text-secondary mb-2">Frames by Filter</div>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(summary.frames_by_filter).map(([filter, count]: [string, any]) => (
                    <div key={filter} className="px-3 py-1 bg-slate-700 rounded text-sm">
                      <span className="text-text-secondary">{filter}:</span>{' '}
                      <span className="font-semibold text-text-primary">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Weather summary */}
            {(summary.temp_avg != null || summary.humidity_avg != null) && (
              <div className="grid grid-cols-5 gap-4 mb-4">
                <div className="p-3 bg-slate-800 rounded">
                  <div className="text-xs text-text-secondary">Temp Range</div>
                  <div className="text-lg font-semibold text-text-primary">
                    {formatNumber(summary.temp_min, 1)} - {formatNumber(summary.temp_max, 1)}C
                  </div>
                </div>
                <div className="p-3 bg-slate-800 rounded">
                  <div className="text-xs text-text-secondary">Avg Temp</div>
                  <div className="text-lg font-semibold text-text-primary">{formatNumber(summary.temp_avg, 1)}C</div>
                </div>
                <div className="p-3 bg-slate-800 rounded">
                  <div className="text-xs text-text-secondary">Avg Humidity</div>
                  <div className="text-lg font-semibold text-text-primary">{formatNumber(summary.humidity_avg, 0)}%</div>
                </div>
                <div className="p-3 bg-slate-800 rounded">
                  <div className="text-xs text-text-secondary">Avg Wind</div>
                  <div className="text-lg font-semibold text-text-primary">{formatNumber(summary.wind_avg, 1)} m/s</div>
                </div>
                <div className="p-3 bg-slate-800 rounded">
                  <div className="text-xs text-text-secondary">Max Wind</div>
                  <div className="text-lg font-semibold text-text-primary">{formatNumber(summary.wind_max, 1)} m/s</div>
                </div>
              </div>
            )}

            {/* Equipment info */}
            {(summary.telescope || summary.camera) && (
              <div className="text-sm text-text-secondary">
                <span className="font-medium">Equipment:</span>{' '}
                {summary.telescope && <span>{summary.telescope}</span>}
                {summary.telescope && summary.camera && <span> + </span>}
                {summary.camera && <span>{summary.camera}</span>}
                {summary.focal_length && <span> @ {summary.focal_length}mm</span>}
                {summary.pixel_scale && <span> ({formatNumber(summary.pixel_scale)}"/px)</span>}
              </div>
            )}
          </div>
        </ChartCard>
      )}

      {/* HFR Timeline Chart */}
      {hfrTimelineData.length > 0 && (
        <ChartCard title="HFR Over Time">
          <div className="p-4">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={hfrTimelineData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                  <YAxis stroke="#9CA3AF" fontSize={10} domain={['auto', 'auto']} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #475569', borderRadius: '4px' }}
                    labelStyle={{ color: '#E2E8F0' }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="hfr" name="HFR" stroke="#60A5FA" dot={{ r: 2 }} />
                  {hfrTimelineData[0]?.detected_stars != null && (
                    <Line type="monotone" dataKey="detected_stars" name="Stars" stroke="#34D399" dot={{ r: 2 }} yAxisId={1} />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </ChartCard>
      )}

      {/* Weather Timeline Chart */}
      {weatherTimelineData.length > 0 && (
        <ChartCard title="Weather Conditions">
          <div className="p-4">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={weatherTimelineData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                  <YAxis yAxisId="temp" stroke="#9CA3AF" fontSize={10} />
                  <YAxis yAxisId="humidity" orientation="right" stroke="#9CA3AF" fontSize={10} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #475569', borderRadius: '4px' }}
                    labelStyle={{ color: '#E2E8F0' }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="temperature" name="Temp (C)" stroke="#F59E0B" yAxisId="temp" dot={false} />
                  <Line type="monotone" dataKey="dew_point" name="Dew Point (C)" stroke="#8B5CF6" yAxisId="temp" dot={false} strokeDasharray="5 5" />
                  <Area type="monotone" dataKey="humidity" name="Humidity (%)" fill="#3B82F6" fillOpacity={0.2} stroke="#3B82F6" yAxisId="humidity" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </ChartCard>
      )}

      {/* Guiding Timeline Chart */}
      {guidingTimelineData.length > 0 && (
        <ChartCard title="Guiding RMS">
          <div className="p-4">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={guidingTimelineData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                  <YAxis stroke="#9CA3AF" fontSize={10} domain={[0, 'auto']} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #475569', borderRadius: '4px' }}
                    labelStyle={{ color: '#E2E8F0' }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="guiding_rms_arcsec" name="Total RMS (arcsec)" stroke="#10B981" dot={{ r: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </ChartCard>
      )}

      {/* Focus Timeline Chart */}
      {focusTimelineData.length > 0 && (
        <ChartCard title="Focus Position vs Temperature">
          <div className="p-4">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={focusTimelineData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                  <YAxis yAxisId="focus" stroke="#9CA3AF" fontSize={10} />
                  <YAxis yAxisId="temp" orientation="right" stroke="#9CA3AF" fontSize={10} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #475569', borderRadius: '4px' }}
                    labelStyle={{ color: '#E2E8F0' }}
                  />
                  <Legend />
                  <Bar dataKey="focuser_position" name="Focus Position" fill="#60A5FA" yAxisId="focus" />
                  <Line type="monotone" dataKey="focuser_temp" name="Focuser Temp (C)" stroke="#F59E0B" yAxisId="temp" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </ChartCard>
      )}

      {/* PHD2 Settle Statistics */}
      {result?.phd2_settle_statistics && (
        <ChartCard title="PHD2 Settle Statistics">
          <div className="p-4">
            <div className="grid grid-cols-5 gap-4 mb-4">
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Total Attempts</div>
                <div className="text-lg font-semibold text-text-primary">{result.phd2_settle_statistics.total_attempts}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Successful</div>
                <div className="text-lg font-semibold text-green-400">{result.phd2_settle_statistics.successful}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Failed</div>
                <div className="text-lg font-semibold text-red-400">{result.phd2_settle_statistics.failed}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Success Rate</div>
                <div className="text-lg font-semibold text-text-primary">{formatPercent(result.phd2_settle_statistics.success_rate)}</div>
              </div>
              <div className="p-3 bg-slate-800 rounded">
                <div className="text-xs text-text-secondary">Avg Settle Time</div>
                <div className="text-lg font-semibold text-text-primary">{formatNumber(result.phd2_settle_statistics.avg_settle_time_sec)}s</div>
              </div>
            </div>

            {/* Failure reasons breakdown */}
            {result.phd2_settle_statistics.failure_reasons && Object.keys(result.phd2_settle_statistics.failure_reasons).length > 0 && (
              <div>
                <div className="text-sm font-medium text-text-secondary mb-2">Failure Reasons</div>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(result.phd2_settle_statistics.failure_reasons).map(([reason, count]: [string, any]) => (
                    <div key={reason} className="px-3 py-1 bg-slate-700 rounded text-sm">
                      <span className="text-text-secondary">{reason}:</span>{' '}
                      <span className="font-semibold text-red-400">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ChartCard>
      )}

      {/* PHD2 Settle Events Table */}
      {result?.phd2_settle_events && result.phd2_settle_events.length > 0 && (
        <ChartCard title="PHD2 Settle Events">
          <div className="p-4">
            <CollapsibleSection title={`Settle Events (${result.phd2_settle_events.length})`}>
              <div className="overflow-auto max-h-64">
                <table className="min-w-full text-sm">
                  <thead className="text-left text-xs text-text-secondary">
                    <tr>
                      <th className="pr-4">Time</th>
                      <th className="pr-4">Status</th>
                      <th className="pr-4">Settle Time</th>
                      <th className="pr-4">Frames</th>
                      <th className="pr-4">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.phd2_settle_events.slice(0, 100).map((evt: any, idx: number) => (
                      <tr key={idx} className="border-t border-slate-700">
                        <td className="pr-4 py-1">{evt.timestamp.replace('T', ' ').substring(0, 19)}</td>
                        <td className="pr-4 py-1">
                          <span className={evt.success ? 'text-green-400' : 'text-red-400'}>
                            {evt.success ? 'Success' : 'Failed'}
                          </span>
                        </td>
                        <td className="pr-4 py-1">{formatNumber(evt.settle_time_sec)}s</td>
                        <td className="pr-4 py-1">{evt.total_frames}</td>
                        <td className="pr-4 py-1 text-text-secondary">{evt.error || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {result.phd2_settle_events.length > 100 && (
                  <div className="text-xs text-text-secondary mt-2">
                    Showing first 100 of {result.phd2_settle_events.length} events
                  </div>
                )}
              </div>
            </CollapsibleSection>
          </div>
        </ChartCard>
      )}

      {/* Frame Details Table */}
      {result?.frames && result.frames.length > 0 && (
        <ChartCard title="Correlated Frame Details">
          <div className="p-4">
            <CollapsibleSection title={`All Frames (${result.frames.length})`}>
              <div className="overflow-auto max-h-96">
                <table className="min-w-full text-sm">
                  <thead className="text-left text-xs text-text-secondary sticky top-0 bg-slate-900">
                    <tr>
                      <th className="pr-3 py-2">#</th>
                      <th className="pr-3 py-2">Time</th>
                      <th className="pr-3 py-2">Filter</th>
                      <th className="pr-3 py-2">Exp</th>
                      <th className="pr-3 py-2">HFR</th>
                      <th className="pr-3 py-2">Stars</th>
                      <th className="pr-3 py-2">Guiding</th>
                      <th className="pr-3 py-2">Focus</th>
                      <th className="pr-3 py-2">Temp</th>
                      <th className="pr-3 py-2">Humidity</th>
                      <th className="pr-3 py-2">Wind</th>
                      <th className="pr-3 py-2">Settle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.frames.map((f: any, idx: number) => (
                      <tr key={idx} className="border-t border-slate-700 hover:bg-slate-800">
                        <td className="pr-3 py-1">{f.exposure_number}</td>
                        <td className="pr-3 py-1 text-text-secondary text-xs">
                          {f.timestamp_utc?.replace('T', ' ').substring(11, 19) || '-'}
                        </td>
                        <td className="pr-3 py-1">{f.filter_name}</td>
                        <td className="pr-3 py-1">{f.duration}s</td>
                        <td className="pr-3 py-1">{formatNumber(f.hfr)}</td>
                        <td className="pr-3 py-1">{f.detected_stars ?? '-'}</td>
                        <td className="pr-3 py-1">{formatNumber(f.guiding_rms_arcsec)}"</td>
                        <td className="pr-3 py-1">{f.focuser_position ?? '-'}</td>
                        <td className="pr-3 py-1">{formatNumber(f.temperature, 1)}C</td>
                        <td className="pr-3 py-1">{formatNumber(f.humidity, 0)}%</td>
                        <td className="pr-3 py-1">{formatNumber(f.wind_speed, 1)}</td>
                        <td className="pr-3 py-1">
                          {f.phd2_settle_success != null && (
                            <span className={f.phd2_settle_success ? 'text-green-400' : 'text-red-400'}>
                              {f.phd2_settle_success ? 'OK' : 'Fail'}
                            </span>
                          )}
                          {f.phd2_settle_success == null && '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CollapsibleSection>
          </div>
        </ChartCard>
      )}
    </div>
  )
}
