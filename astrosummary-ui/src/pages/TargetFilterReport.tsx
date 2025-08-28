import { useMemo } from 'react'
import { useApp } from '../context/AppContext'
import ChartCard from '../components/ChartCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function TargetFilterReport() {
  const { frames } = useApp()

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
  {/* Scan is available in the sidebar */}

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
