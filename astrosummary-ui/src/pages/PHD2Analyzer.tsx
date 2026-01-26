import { useState } from 'react'
import ChartCard from '../components/ChartCard'
import { API_URL } from '../lib/apiConfig'

interface PHD2SettleEvent {
  timestamp: string
  success: boolean
  status: number
  total_frames: number
  dropped_frames: number
  settle_time_sec: number
  error: string | null
  failure_reason: string | null
}

interface PHD2SessionStats {
  file: string
  date: string
  total: number
  successful: number
  failed: number
  success_rate: number
}

interface PHD2Statistics {
  total_attempts: number
  successful: number
  failed: number
  success_rate: number
  avg_settle_time_sec: number
  min_settle_time_sec: number
  max_settle_time_sec: number
  median_settle_time_sec: number
  frame_distribution: Record<number, number>
  failure_reasons: Record<string, number>
}

interface PHD2AnalyzeResponse {
  success: boolean
  error: string | null
  statistics: PHD2Statistics | null
  sessions: PHD2SessionStats[]
  events: PHD2SettleEvent[]
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds <= 0) return '0s'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs.toFixed(0)}s`
}

function ProgressBar({ value, max, color = 'bg-accent-primary' }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="h-4 bg-slate-700 rounded flex-1">
      <div style={{ width: `${pct}%` }} className={`h-4 ${color} rounded`} />
    </div>
  )
}

export default function PHD2Analyzer() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PHD2AnalyzeResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showAllEvents, setShowAllEvents] = useState(false)
  const [eventFilter, setEventFilter] = useState<'all' | 'success' | 'failed'>('all')

  async function submit() {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API_URL}/phd2/analyze_upload`, { method: 'POST', body: fd })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const json = await res.json()
      setResult(json)
    } catch (e: any) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const filteredEvents = (result?.events ?? []).filter(e => {
    if (eventFilter === 'success') return e.success
    if (eventFilter === 'failed') return !e.success
    return true
  })

  const displayedEvents = showAllEvents ? filteredEvents : filteredEvents.slice(0, 50)

  return (
    <div className="space-y-4">
      <ChartCard title="PHD2 Settle Statistics Analyzer">
        <div className="p-4">
          <div className="mb-4">
            <p className="text-sm text-text-secondary mb-2">
              Upload a PHD2 Debug Log file (PHD2_DebugLog_*.txt) to analyze settling performance.
            </p>
            <input
              type="file"
              accept=".txt"
              onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
            />
            <div className="mt-2">
              <button
                className="px-3 py-2 rounded bg-accent-primary text-black disabled:opacity-60"
                onClick={submit}
                disabled={!file || loading}
              >
                {loading ? 'Analyzing...' : 'Analyze'}
              </button>
            </div>
          </div>

          {error && <div className="mt-2 text-red-400">{error}</div>}

          {result && !result.success && (
            <div className="mt-4 p-3 bg-red-900/30 border border-red-700 rounded text-red-300">
              {result.error || 'Analysis failed'}
            </div>
          )}

          {result && result.success && result.statistics && (
            <div className="mt-4 space-y-6 text-sm text-text-secondary">
              {/* Summary Cards */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-slate-800 rounded">
                  <div className="text-xs text-text-secondary">Total Settles</div>
                  <div className="text-2xl font-semibold text-text-primary">{result.statistics.total_attempts}</div>
                </div>
                <div className="p-3 bg-slate-800 rounded border-l-4 border-green-500">
                  <div className="text-xs text-green-400">Successful</div>
                  <div className="text-2xl font-semibold text-green-400">{result.statistics.successful}</div>
                </div>
                <div className="p-3 bg-slate-800 rounded border-l-4 border-red-500">
                  <div className="text-xs text-red-400">Failed</div>
                  <div className="text-2xl font-semibold text-red-400">{result.statistics.failed}</div>
                </div>
                <div className="p-3 bg-slate-800 rounded border-l-4 border-accent-primary">
                  <div className="text-xs text-accent-primary">Success Rate</div>
                  <div className="text-2xl font-semibold text-accent-primary">{result.statistics.success_rate.toFixed(1)}%</div>
                </div>
              </div>

              {/* Settle Time Stats */}
              <div>
                <div className="font-semibold mb-3 text-text-primary">Settle Time (Successful Only)</div>
                <div className="grid grid-cols-4 gap-4">
                  <div className="p-3 bg-slate-800 rounded">
                    <div className="text-xs text-text-secondary">Average</div>
                    <div className="text-lg font-semibold text-text-primary">{formatTime(result.statistics.avg_settle_time_sec)}</div>
                  </div>
                  <div className="p-3 bg-slate-800 rounded">
                    <div className="text-xs text-text-secondary">Median</div>
                    <div className="text-lg font-semibold text-text-primary">{formatTime(result.statistics.median_settle_time_sec)}</div>
                  </div>
                  <div className="p-3 bg-slate-800 rounded">
                    <div className="text-xs text-text-secondary">Min</div>
                    <div className="text-lg font-semibold text-text-primary">{formatTime(result.statistics.min_settle_time_sec)}</div>
                  </div>
                  <div className="p-3 bg-slate-800 rounded">
                    <div className="text-xs text-text-secondary">Max</div>
                    <div className="text-lg font-semibold text-text-primary">{formatTime(result.statistics.max_settle_time_sec)}</div>
                  </div>
                </div>
              </div>

              {/* Frame Distribution */}
              {result.statistics.frame_distribution && Object.keys(result.statistics.frame_distribution).length > 0 && (
                <div>
                  <div className="font-semibold mb-3 text-text-primary">Frame Count Distribution</div>
                  <div className="space-y-1">
                    {Object.entries(result.statistics.frame_distribution)
                      .sort(([a], [b]) => Number(a) - Number(b))
                      .map(([frames, count]) => {
                        const max = Math.max(...Object.values(result.statistics!.frame_distribution))
                        const pct = (count / result.statistics!.total_attempts * 100).toFixed(1)
                        return (
                          <div key={frames} className="flex items-center text-sm">
                            <div className="w-20 text-right mr-2 text-text-secondary">{frames} frames</div>
                            <ProgressBar value={count} max={max} />
                            <div className="w-20 text-right ml-2 text-text-secondary">{count} ({pct}%)</div>
                          </div>
                        )
                      })}
                  </div>
                </div>
              )}

              {/* Failure Reasons */}
              {result.statistics.failure_reasons && Object.keys(result.statistics.failure_reasons).length > 0 && (
                <div>
                  <div className="font-semibold mb-3 text-text-primary">Failure Breakdown</div>
                  <div className="space-y-1">
                    {Object.entries(result.statistics.failure_reasons)
                      .sort(([, a], [, b]) => b - a)
                      .map(([reason, count]) => {
                        const max = Math.max(...Object.values(result.statistics!.failure_reasons))
                        const pct = (count / result.statistics!.failed * 100).toFixed(1)
                        const labels: Record<string, string> = {
                          'timeout': 'Timeout',
                          'lost_star': 'Lost Star',
                          'guiding_stopped': 'Guiding Stopped',
                          'other': 'Other'
                        }
                        return (
                          <div key={reason} className="flex items-center text-sm">
                            <div className="w-32 text-right mr-2 text-text-secondary">{labels[reason] || reason}</div>
                            <ProgressBar value={count} max={max} color="bg-red-500" />
                            <div className="w-20 text-right ml-2 text-text-secondary">{count} ({pct}%)</div>
                          </div>
                        )
                      })}
                  </div>
                </div>
              )}

              {/* Per-Session Stats */}
              {result.sessions && result.sessions.length > 0 && (
                <div>
                  <div className="font-semibold mb-3 text-text-primary">Per-Session Breakdown</div>
                  <div className="overflow-auto max-h-64">
                    <table className="min-w-full text-sm">
                      <thead className="text-left text-xs text-text-secondary">
                        <tr>
                          <th className="pr-3">Date</th>
                          <th className="pr-3">File</th>
                          <th className="pr-3 text-right">Total</th>
                          <th className="pr-3 text-right">Success</th>
                          <th className="pr-3 text-right">Failed</th>
                          <th className="pr-3 text-right">Rate</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.sessions.map((s, idx) => (
                          <tr key={idx} className="border-t border-slate-700">
                            <td className="pr-3 py-1">{s.date}</td>
                            <td className="pr-3 py-1 text-xs text-text-secondary truncate max-w-xs" title={s.file}>
                              {s.file.split(/[/\\]/).pop()}
                            </td>
                            <td className="pr-3 py-1 text-right">{s.total}</td>
                            <td className="pr-3 py-1 text-right text-green-400">{s.successful}</td>
                            <td className="pr-3 py-1 text-right text-red-400">{s.failed}</td>
                            <td className="pr-3 py-1 text-right font-medium">
                              <span className={s.success_rate >= 80 ? 'text-green-400' : s.success_rate >= 60 ? 'text-yellow-400' : 'text-red-400'}>
                                {s.success_rate.toFixed(1)}%
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Settle Events Table */}
              {result.events && result.events.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="font-semibold text-text-primary">
                      Settle Events ({filteredEvents.length} of {result.events.length})
                    </div>
                    <div className="flex items-center gap-3">
                      <select
                        className="px-2 py-1 text-sm rounded bg-slate-700 border border-slate-600 text-text-primary"
                        value={eventFilter}
                        onChange={(e) => setEventFilter(e.target.value as any)}
                      >
                        <option value="all">All Events</option>
                        <option value="success">Successful Only</option>
                        <option value="failed">Failed Only</option>
                      </select>
                      {filteredEvents.length > 50 && (
                        <button
                          className="text-xs px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-text-secondary"
                          onClick={() => setShowAllEvents(!showAllEvents)}
                        >
                          {showAllEvents ? 'Show First 50' : `Show All ${filteredEvents.length}`}
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="overflow-auto max-h-80">
                    <table className="min-w-full text-sm">
                      <thead className="text-left text-xs text-text-secondary sticky top-0 bg-bg-card">
                        <tr>
                          <th className="pr-3 py-1">Timestamp</th>
                          <th className="pr-3 py-1">Status</th>
                          <th className="pr-3 py-1 text-right">Frames</th>
                          <th className="pr-3 py-1 text-right">Time</th>
                          <th className="pr-3 py-1">Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {displayedEvents.map((e, idx) => (
                          <tr key={idx} className={`border-t border-slate-700 ${e.success ? '' : 'bg-red-900/20'}`}>
                            <td className="pr-3 py-1 text-xs">{e.timestamp.replace('T', ' ')}</td>
                            <td className="pr-3 py-1">
                              <span className={`inline-block px-2 py-0.5 rounded text-xs ${e.success ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                                {e.success ? 'OK' : 'FAIL'}
                              </span>
                            </td>
                            <td className="pr-3 py-1 text-right">{e.total_frames}</td>
                            <td className="pr-3 py-1 text-right">{formatTime(e.settle_time_sec)}</td>
                            <td className="pr-3 py-1 text-xs text-text-secondary truncate max-w-xs" title={e.error || ''}>
                              {e.failure_reason || e.error || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </ChartCard>
    </div>
  )
}
