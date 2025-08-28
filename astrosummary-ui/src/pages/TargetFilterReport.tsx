import { useMemo } from 'react'
import { useApp } from '../context/AppContext'
import ChartCard from '../components/ChartCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

// read palette from localStorage to match RatioPlanner themes
const palettes: Record<string, any> = {
  highContrast: {
    axis: '#E5E7EB',
    total: '#3B82F6'
  },
  colorBlind: {
    axis: '#E6E6E6',
    total: '#E69F00'
  },
  muted: {
    axis: '#9CA3AF',
    total: '#60A5FA'
  }
}

function getColors() {
  try { const key = localStorage.getItem('chartPalette') || 'muted'; return palettes[key] || palettes.muted } catch { return palettes.muted }
}

export default function TargetFilterReport() {
  const { frames } = useApp()
  const colors = getColors()

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
              <XAxis dataKey="filter" tick={{ fill: colors.axis }} />
              <YAxis tick={{ fill: colors.axis }} />
              <Tooltip contentStyle={{ background: '#0F172A', border: '1px solid #1F2937', color: '#F9FAFB' }} />
              <Bar dataKey="hours" name="Hours" fill={colors.total} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>
    </div>
  )
}
