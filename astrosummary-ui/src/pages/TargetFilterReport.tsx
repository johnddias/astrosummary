import { useMemo, useState } from 'react'
import { useApp } from '../context/AppContext'
import { scanFrames } from '../lib/scan'
import ChartCard from '../components/ChartCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function TargetFilterReport() {
  const { frames, setFrames, recurse, backendPath } = useApp()
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

  const rows = useMemo(() => {
    const by = new Map<string, number>()
    for (const f of frames) {
      if (f.frameType !== 'LIGHT') continue
      const k = f.filter || 'Unknown'
      by.set(k, (by.get(k) || 0) + f.exposure_s / 3600)
    }
    return Array.from(by.entries())
      .map(([filter, hours]) => ({ filter, hours }))
      .sort((a, b) => a.filter.localeCompare(b.filter))
  }, [frames])

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
      </div>

      {scanning && (
        <div className="mt-1 h-1 bg-slate-700 rounded overflow-hidden">
          <div className="animate-pulse bg-accent-primary h-1 w-full"></div>
        </div>
      )}

      <div className="text-xs text-text-secondary">{status}</div>

      <ChartCard title="Total Hours by Filter (all targets)">
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows}>
              <XAxis dataKey="filter" tick={{ fill: '#9CA3AF' }} />
              <YAxis tick={{ fill: '#9CA3AF' }} />
              <Tooltip contentStyle={{ background: '#0F172A', border: '1px solid #1F2937', color: '#F9FAFB' }} />
              <Bar dataKey="hours" name="Hours" fill="#FFD700" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>
    </div>
  )
}
