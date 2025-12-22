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
            </div>
          )}
        </div>
      </ChartCard>
    </div>
  )
}
