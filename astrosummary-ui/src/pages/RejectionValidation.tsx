import { useState, useEffect } from 'react'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts'
import type { ValidationResponse, ValidationResult, LightFrame, RejectionData } from '../lib/types'
import { API_URL } from '../lib/apiConfig'

interface RejectionValidationProps {
  frames: LightFrame[]
  rejectionData: RejectionData | null
}

const FILTER_COLORS: Record<string, string> = {
  'Ha': '#ff4444',
  'OIII': '#44ff44',
  'SII': '#4444ff',
  'R': '#ff8888',
  'G': '#88ff88',
  'B': '#8888ff',
  'L': '#aaaaaa',
}

const STATUS_COLORS: Record<string, string> = {
  'CORRECT_REJECT': '#22c55e',
  'CORRECT_ACCEPT': '#3b82f6',
  'FALSE_POSITIVE': '#ef4444',
  'FALSE_NEGATIVE': '#f59e0b',
}

export default function RejectionValidation({ frames, rejectionData }: RejectionValidationProps) {
  const [validationResults, setValidationResults] = useState<ValidationResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [phd2LogPath, setPhd2LogPath] = useState<string>('')
  const [sortColumn, setSortColumn] = useState<keyof ValidationResult | 'quality_score'>('quality_score')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [progress, setProgress] = useState<{ current: number; total: number; status?: string } | null>(null)
  const [filterTypeFilter, setFilterTypeFilter] = useState<string>('all')
  const [dateFilter, setDateFilter] = useState<string>('all')

  // Check if we have the required data
  const canValidate = frames.length > 0 && rejectionData !== null

  const handleValidate = async () => {
    if (!canValidate) {
      setError('Missing frames or rejection data')
      return
    }

    setIsLoading(true)
    setError(null)
    setProgress({ current: 0, total: frames.length, status: 'Starting...' })

    try {
      console.log('Sending validation request with SSE streaming...')
      const response = await fetch(`${API_URL}/analyze/validate_rejections_stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          frames: frames,
          rejection_data: rejectionData,
          phd2_log_path: phd2LogPath || null
        })
      })

      if (!response.ok) {
        throw new Error(`Validation failed: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Process complete SSE messages
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === 'progress') {
                setProgress({
                  current: data.current,
                  total: data.total,
                  status: data.status
                })
              } else if (data.type === 'complete') {
                console.log('Validation complete, results:', data.data.results.length)
                setValidationResults(data.data as ValidationResponse)
                setProgress({ current: data.data.results.length, total: data.data.results.length, status: 'Complete!' })
              } else if (data.type === 'error') {
                throw new Error(data.message)
              }
            } catch (parseError) {
              console.warn('Failed to parse SSE message:', line)
            }
          }
        }
      }
    } catch (err) {
      console.error('Validation error:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
      setTimeout(() => setProgress(null), 2000)
    }
  }

  const handleExportCSV = async () => {
    if (!validationResults) return

    try {
      const response = await fetch(`${API_URL}/analyze/export_validation_csv`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(validationResults)
      })

      if (!response.ok) {
        throw new Error(`CSV export failed: ${response.statusText}`)
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'rejection_validation.csv'
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      console.error('CSV export error:', err)
      alert(`Failed to export CSV: ${err}`)
    }
  }

  const handleSort = (column: keyof ValidationResult | 'quality_score') => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('desc')
    }
  }

  const getSortedResults = (): ValidationResult[] => {
    if (!validationResults) return []

    // Apply filters
    let filtered = validationResults.results

    if (filterTypeFilter !== 'all') {
      filtered = filtered.filter(r => r.filter === filterTypeFilter)
    }

    if (dateFilter !== 'all') {
      filtered = filtered.filter(r => r.date === dateFilter)
    }

    // Sort
    return [...filtered].sort((a, b) => {
      let aValue: any
      let bValue: any

      if (sortColumn === 'quality_score') {
        aValue = a.metrics.quality_score
        bValue = b.metrics.quality_score
      } else {
        aValue = a[sortColumn]
        bValue = b[sortColumn]
      }

      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortDirection === 'asc'
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue)
      }

      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortDirection === 'asc' ? aValue - bValue : bValue - aValue
      }

      return 0
    })
  }

  // Get unique filters and dates for filter dropdowns
  const uniqueFilters = validationResults
    ? Array.from(new Set(validationResults.results.map(r => r.filter))).sort()
    : []

  const uniqueDates = validationResults
    ? Array.from(new Set(validationResults.results.map(r => r.date))).sort()
    : []

  // Prepare scatter plot data
  const scatterData = validationResults?.results.map(result => ({
    name: result.filename,
    quality_score: result.metrics.quality_score,
    rejected: result.rejected_by_wbpp ? 1 : 0,
    filter: result.filter,
    status: result.validation_status,
    snr: result.metrics.snr,
    fwhm: result.metrics.fwhm,
    eccentricity: result.metrics.eccentricity,
    star_count: result.metrics.star_count,
    phd2_rms: result.metrics.phd2_rms,
  })) || []

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-gray-900 border border-gray-700 p-3 rounded shadow-lg text-xs">
          <p className="font-semibold text-white mb-1">{data.name}</p>
          <p className="text-gray-300">Filter: <span className="font-medium" style={{ color: FILTER_COLORS[data.filter] || '#ffffff' }}>{data.filter}</span></p>
          <p className="text-gray-300">Status: <span className="font-medium" style={{ color: STATUS_COLORS[data.status] }}>{data.status}</span></p>
          <p className="text-gray-300">Quality Score: <span className="font-medium text-white">{data.quality_score.toFixed(3)}</span></p>
          <p className="text-gray-300">SNR: {data.snr.toFixed(2)}</p>
          <p className="text-gray-300">FWHM: {data.fwhm.toFixed(2)}</p>
          <p className="text-gray-300">Eccentricity: {data.eccentricity.toFixed(3)}</p>
          <p className="text-gray-300">Stars: {data.star_count}</p>
          {data.phd2_rms && (
            <p className="text-gray-300">PHD2 RMS: {data.phd2_rms.toFixed(2)}</p>
          )}
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-white mb-4">Rejection Validation Dashboard</h2>

        <div className="mb-4 text-gray-300">
          <p>Validate PixInsight WBPP rejection decisions against objective quality metrics.</p>
          <p className="text-sm text-gray-400 mt-1">
            Identifies false positives (good frames incorrectly rejected) and false negatives (poor frames incorrectly accepted).
          </p>
        </div>

        {!canValidate && (
          <div className="bg-yellow-900 border border-yellow-700 text-yellow-200 p-4 rounded mb-4">
            Please scan frames and upload a rejection log first.
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              PHD2 Log Path or Directory (optional)
            </label>
            <input
              type="text"
              value={phd2LogPath}
              onChange={(e) => setPhd2LogPath(e.target.value)}
              placeholder="e.g., Y:\PHD2_Logs\ or Y:\PHD2_GuideLog_2025-12-07.txt"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400"
            />
            <p className="text-xs text-gray-400 mt-1">
              Provide a single log file or a directory containing multiple PHD2 logs. Logs will be auto-selected based on frame dates.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleValidate}
              disabled={!canValidate || isLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium rounded transition"
            >
              {isLoading ? 'Analyzing...' : 'Run Validation Analysis'}
            </button>

            {validationResults && (
              <button
                onClick={handleExportCSV}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded transition"
              >
                Export Results (CSV)
              </button>
            )}
          </div>

          {progress && (
            <div className="mt-4">
              <div className="flex justify-between text-sm text-gray-300 mb-2">
                <span>{progress.status || 'Analyzing frames...'}</span>
                <span>{progress.current} / {progress.total} ({Math.round((progress.current / progress.total) * 100)}%)</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                <div
                  className="h-3 bg-blue-600 transition-all duration-300"
                  style={{ width: `${(progress.current / progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mt-4 bg-red-900 border border-red-700 text-red-200 p-4 rounded">
            Error: {error}
          </div>
        )}
      </div>

      {validationResults && (
        <>
          {/* Summary Statistics */}
          <div className="bg-gray-800 rounded-lg shadow-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Summary Statistics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gray-700 p-4 rounded">
                <div className="text-2xl font-bold text-white">{validationResults.summary.total_frames}</div>
                <div className="text-sm text-gray-300">Total Frames</div>
              </div>
              <div className="bg-green-900 p-4 rounded">
                <div className="text-2xl font-bold text-white">
                  {validationResults.summary.correct_rejects + validationResults.summary.correct_accepts}
                </div>
                <div className="text-sm text-gray-300">Correct Decisions</div>
                <div className="text-xs text-gray-400 mt-1">
                  {(validationResults.summary.accuracy * 100).toFixed(1)}% accuracy
                </div>
              </div>
              <div className="bg-red-900 p-4 rounded">
                <div className="text-2xl font-bold text-white">{validationResults.summary.false_positives}</div>
                <div className="text-sm text-gray-300">False Positives</div>
                <div className="text-xs text-gray-400 mt-1">Good frames rejected</div>
              </div>
              <div className="bg-orange-900 p-4 rounded">
                <div className="text-2xl font-bold text-white">{validationResults.summary.false_negatives}</div>
                <div className="text-sm text-gray-300">False Negatives</div>
                <div className="text-xs text-gray-400 mt-1">Poor frames accepted</div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
              <div className="bg-gray-700 p-3 rounded">
                <div className="text-sm text-gray-300">WBPP Reject Rate</div>
                <div className="text-lg font-semibold text-white">
                  {(validationResults.summary.wbpp_reject_rate * 100).toFixed(1)}%
                </div>
              </div>
              <div className="bg-gray-700 p-3 rounded">
                <div className="text-sm text-gray-300">Mean Quality (Rejected)</div>
                <div className="text-lg font-semibold text-white">
                  {validationResults.summary.mean_quality_rejected.toFixed(3)}
                </div>
              </div>
              <div className="bg-gray-700 p-3 rounded">
                <div className="text-sm text-gray-300">Mean Quality (Accepted)</div>
                <div className="text-lg font-semibold text-white">
                  {validationResults.summary.mean_quality_accepted.toFixed(3)}
                </div>
              </div>
            </div>
          </div>

          {/* Scatter Plot */}
          <div className="bg-gray-800 rounded-lg shadow-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Quality Score vs Rejection Status</h3>
            <ResponsiveContainer width="100%" height={400}>
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  type="number"
                  dataKey="quality_score"
                  name="Quality Score"
                  domain={[0, 1]}
                  stroke="#9ca3af"
                  label={{ value: 'Quality Score', position: 'insideBottom', offset: -10, fill: '#9ca3af' }}
                />
                <YAxis
                  type="number"
                  dataKey="rejected"
                  name="Rejection Status"
                  domain={[-0.2, 1.2]}
                  ticks={[0, 1]}
                  tickFormatter={(value) => value === 0 ? 'Accepted' : 'Rejected'}
                  stroke="#9ca3af"
                  label={{ value: 'Status', angle: -90, position: 'insideLeft', fill: '#9ca3af' }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ paddingTop: '20px' }}
                  formatter={(value, entry: any) => {
                    const status = entry.payload?.status || value
                    return <span style={{ color: STATUS_COLORS[status] || '#ffffff' }}>{status}</span>
                  }}
                />
                <Scatter data={scatterData} shape="circle">
                  {scatterData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={STATUS_COLORS[entry.status]} opacity={0.7} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>

            <div className="mt-4 flex flex-wrap gap-3 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: STATUS_COLORS.CORRECT_REJECT }}></div>
                <span className="text-gray-300">Correct Reject</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: STATUS_COLORS.CORRECT_ACCEPT }}></div>
                <span className="text-gray-300">Correct Accept</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: STATUS_COLORS.FALSE_POSITIVE }}></div>
                <span className="text-gray-300">False Positive (Good frame rejected)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: STATUS_COLORS.FALSE_NEGATIVE }}></div>
                <span className="text-gray-300">False Negative (Poor frame accepted)</span>
              </div>
            </div>
          </div>

          {/* Data Table */}
          <div className="bg-gray-800 rounded-lg shadow-lg p-6">
            <h3 className="text-xl font-bold text-white mb-4">Detailed Results</h3>

            {/* Filters */}
            <div className="flex gap-4 mb-4">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-300">Filter:</label>
                <select
                  value={filterTypeFilter}
                  onChange={(e) => setFilterTypeFilter(e.target.value)}
                  className="px-3 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                >
                  <option value="all">All Filters</option>
                  {uniqueFilters.map(filter => (
                    <option key={filter} value={filter}>{filter}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-300">Date:</label>
                <select
                  value={dateFilter}
                  onChange={(e) => setDateFilter(e.target.value)}
                  className="px-3 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                >
                  <option value="all">All Dates</option>
                  {uniqueDates.map(date => (
                    <option key={date} value={date}>{date}</option>
                  ))}
                </select>
              </div>

              <div className="flex-1"></div>

              <div className="text-sm text-gray-400">
                Showing {getSortedResults().length} of {validationResults.results.length} frames
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm text-gray-300">
                <thead className="text-xs uppercase bg-gray-700 text-gray-400">
                  <tr>
                    <th className="px-3 py-2 cursor-pointer hover:bg-gray-600" onClick={() => handleSort('filename')}>
                      Filename {sortColumn === 'filename' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-3 py-2 cursor-pointer hover:bg-gray-600" onClick={() => handleSort('target')}>
                      Target {sortColumn === 'target' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-3 py-2 cursor-pointer hover:bg-gray-600" onClick={() => handleSort('filter')}>
                      Filter {sortColumn === 'filter' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-3 py-2 cursor-pointer hover:bg-gray-600" onClick={() => handleSort('quality_score')}>
                      Quality {sortColumn === 'quality_score' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-3 py-2">SNR</th>
                    <th className="px-3 py-2">FWHM</th>
                    <th className="px-3 py-2">Ecc</th>
                    <th className="px-3 py-2">Stars</th>
                    <th className="px-3 py-2">PHD2</th>
                    <th className="px-3 py-2">WBPP</th>
                    <th className="px-3 py-2 cursor-pointer hover:bg-gray-600" onClick={() => handleSort('validation_status')}>
                      Status {sortColumn === 'validation_status' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {getSortedResults().map((result, idx) => (
                    <tr key={idx} className="border-b border-gray-700 hover:bg-gray-700">
                      <td className="px-3 py-2 text-xs font-mono" title={result.filename}>
                        {result.filename.length > 30 ? result.filename.substring(0, 30) + '...' : result.filename}
                      </td>
                      <td className="px-3 py-2">{result.target}</td>
                      <td className="px-3 py-2">
                        <span style={{ color: FILTER_COLORS[result.filter] || '#ffffff' }}>
                          {result.filter}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-semibold">
                        {result.metrics.quality_score.toFixed(3)}
                      </td>
                      <td className="px-3 py-2">{result.metrics.snr.toFixed(1)}</td>
                      <td className="px-3 py-2">{result.metrics.fwhm.toFixed(2)}</td>
                      <td className="px-3 py-2">{result.metrics.eccentricity.toFixed(3)}</td>
                      <td className="px-3 py-2">{result.metrics.star_count}</td>
                      <td className="px-3 py-2">
                        {result.metrics.phd2_rms ? result.metrics.phd2_rms.toFixed(2) : '-'}
                      </td>
                      <td className="px-3 py-2">
                        {result.rejected_by_wbpp ? (
                          <span className="text-red-400">Rejected</span>
                        ) : (
                          <span className="text-green-400">Accepted</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className="px-2 py-1 rounded text-xs font-medium"
                          style={{
                            backgroundColor: STATUS_COLORS[result.validation_status] + '33',
                            color: STATUS_COLORS[result.validation_status]
                          }}
                        >
                          {result.validation_status.replace('_', ' ')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
