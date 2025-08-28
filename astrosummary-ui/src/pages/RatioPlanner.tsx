import { useMemo, useState } from 'react'
import { useApp } from '../context/AppContext'
import { totalsByTarget, computeEqualGoal, planToTotalHours, balanceDeficits } from '../lib/analysis'
import ChartCard from '../components/ChartCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
type RatioSource = 'Equal' | 'Custom'

export default function RatioPlanner() {
  const { frames, desiredHours, setDesiredHours } = useApp()
  const [ratioSource, setRatioSource] = useState<RatioSource>('Equal')
  const [customText, setCustomText] = useState<string>('')

  const goal = useMemo(() => {
    if (ratioSource === 'Custom') {
      const out: Record<string, number> = {}
      customText
        .replace(/,/g, ' ')
        .split(/\s+/)
        .map(tok => tok.trim())
        .filter(Boolean)
        .forEach(tok => {
          const [k, v] = tok.includes('=') ? tok.split('=') : [tok, '1']
          const key = (k || '').trim()
          const val = Number((v || '').trim())
          if (key && val > 0) out[key] = val
        })
      return out
    }
    return computeEqualGoal(frames)
  }, [ratioSource, customText, frames])

  const totals = useMemo(() => totalsByTarget(frames), [frames])
  const targets = useMemo(() => Object.keys(totals).sort(), [totals])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">

        <div className="flex flex-col">
          <label className="text-xs text-text-secondary">Desired hours per target</label>
          <input
            type="number"
            step="0.5"
            className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
            placeholder="e.g. 20"
            value={desiredHours ?? 20}
            onChange={(e) => setDesiredHours(e.target.value ? Number(e.target.value) : 20)}
          />
        </div>

        <div className="flex flex-col">
          <label className="text-xs text-text-secondary">Ratio source</label>
          <select
            className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
            value={ratioSource}
            onChange={(e) => setRatioSource(e.target.value as RatioSource)}
          >
            <option>Equal</option>
            <option>Custom</option>
          </select>
        </div>

  {/* Preset option removed - only Equal and Custom are supported */}

        {ratioSource === 'Custom' && (
          <div className="flex-1 min-w-[260px]">
            <label className="text-xs text-text-secondary">Custom ratios (e.g., Ha=2 OIII=1 SII=1)</label>
            <input
              className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
              placeholder="Ha=2 OIII=1 SII=1"
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
            />
          </div>
        )}
      </div>

  {/* Scanning moved to Sidebar; status is available in AppContext if needed */}

      {targets.length === 0 && (
        <div className="text-text-secondary">No LIGHT frames yet — run Scan from the sidebar.</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {targets.map(target => {
          const current = totals[target] || {}
          const { need } = (desiredHours && desiredHours > 0)
            ? planToTotalHours(current, goal, desiredHours)
            : balanceDeficits(current, goal)

          const rows = Object.keys({ ...current, ...goal })
            .sort()
            .map(filter => {
              const capturedH = (current[filter] || 0) / 3600
              const neededH = (need[filter] || 0) / 3600
              return {
                filter,
                captured: Math.min(capturedH, Math.max(capturedH, neededH)),
                needed: Math.max(0, neededH - capturedH),
                overshoot: Math.max(0, capturedH - neededH),
              }
            })
            .filter(r => r.captured > 0 || r.needed > 0 || r.overshoot > 0)

          if (rows.length === 0) return null

          return (
            <ChartCard key={target} title={`${target}`}>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows}>
                    <XAxis dataKey="filter" tick={{ fill: '#ffffffff' }} />
                    <YAxis tick={{ fill: '#ffffffff' }} />
                    <Tooltip
                      contentStyle={{ background: '#0F172A', border: '1px solid #1F2937', color: '#F9FAFB' }}
                      formatter={(val: any, name: any) => [`${Number(val).toFixed(2)} h`, name]}
                    />
                    <Legend />
                    <Bar dataKey="captured"  stackId="a" name="Captured (h)"  fill="#20c945de" />
                    <Bar dataKey="needed"    stackId="a" name="Needed (h)"    fill="#4892dbff" />
                    <Bar dataKey="overshoot" stackId="a" name="Overshoot (h)" fill="hsla(64, 80%, 43%, 1.00)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          )
        })}
      </div>
    </div>
  )
}
