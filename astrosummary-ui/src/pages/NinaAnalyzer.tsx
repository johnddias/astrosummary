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
    } catch (e: any) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

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
                <div className="font-semibold">Segments (first 50)</div>
                <div className="mt-2 overflow-auto max-h-64">
                  <table className="min-w-full text-sm">
                    <thead className="text-left text-xs text-gray-500">
                      <tr><th>start</th><th>end</th><th>label</th><th>dur(s)</th><th>meta</th></tr>
                    </thead>
                    <tbody>
                      {result.segments.slice(0,50).map((s:any, idx:number)=> (
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
