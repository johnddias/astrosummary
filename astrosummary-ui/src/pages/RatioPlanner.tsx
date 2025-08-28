import { useMemo, useState, useEffect } from 'react'
import { useApp } from '../context/AppContext'
import { totalsByTarget, computeEqualGoal } from '../lib/analysis'
import ChartCard from '../components/ChartCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { normalizeFilter } from '../lib/filters'
export default function RatioPlanner() {
  const { frames, desiredHours, setDesiredHours } = useApp()
  const [customText, setCustomText] = useState<string>('')
  const [colorScheme, setColorScheme] = useState<string>(() => {
    try { return localStorage.getItem('chartPalette') || 'muted' } catch { return 'muted' }
  })

  useEffect(() => {
    try { localStorage.setItem('chartPalette', colorScheme) } catch {}
  }, [colorScheme])

  const palettes: Record<string, any> = {
    highContrast: {
      captured: '#10B981', // emerald
      needed: '#3B82F6', // blue
      overshoot: '#F59E0B', // amber
      targetStroke: '#F3F4F6',
      targetFill: 'rgba(255,255,255,0.06)',
      axis: '#E5E7EB'
    },
    colorBlind: {
      captured: '#0072B2',
      needed: '#E69F00',
      overshoot: '#009E73',
      targetStroke: '#FFFFFF',
      targetFill: 'rgba(255,255,255,0.06)',
      axis: '#E6E6E6'
    },
    muted: {
      captured: '#34D399',
      needed: '#60A5FA',
      overshoot: '#FCA5A5',
      targetStroke: '#CBD5E1',
      targetFill: 'rgba(203,213,225,0.06)',
      axis: '#9CA3AF'
    }
  }
  const colors = palettes[colorScheme] || palettes.muted

  const goal = useMemo(() => {
    // Always use custom ratios if provided, otherwise fall back to equal goal
    if (customText && customText.trim()) {
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
  }, [customText, frames])

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

        <div className="flex-1 min-w-[260px]">
          <label className="text-xs text-text-secondary">Custom ratios (e.g., Ha=2 OIII=1 SII=1)</label>
          <input
            className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
            placeholder="Ha=2 OIII=1 SII=1"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
          />
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-text-secondary">Color scheme</label>
          <select
            className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
            value={colorScheme}
            onChange={(e) => setColorScheme(e.target.value)}
          >
            <option value="muted">Muted (default)</option>
            <option value="highContrast">High contrast</option>
            <option value="colorBlind">Color-blind friendly</option>
          </select>
        </div>
      </div>

  {/* Scanning moved to Sidebar; status is available in AppContext if needed */}

      {targets.length === 0 && (
        <div className="text-text-secondary">No LIGHT frames yet — run Scan from the sidebar.</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {targets.map(target => {
          const current = totals[target] || {}
          // Build normalized goal weights and compute totalSeconds for target calculation
          const normGoal: Record<string, number> = {}
          let sumW = 0
          for (const [raw, w] of Object.entries(goal)) {
            const k = normalizeFilter(raw)
            normGoal[k] = (normGoal[k] || 0) + (w || 0)
            sumW += (w || 0)
          }
          const totalSeconds = (desiredHours && desiredHours > 0)
            ? desiredHours * 3600
            : Object.values(current).reduce((a, b) => a + (b || 0), 0)

          const rows = Object.keys({ ...current, ...goal })
            .sort()
            .map(filter => {
              const capturedH = (current[filter] || 0) / 3600
              // compute this filter's target hours from normalized goal weights
              const weight = normGoal[filter] || 0
              const targetSec = sumW > 0 ? (weight / sumW) * totalSeconds : 0
              const targetH = targetSec / 3600
              const captured = Number(capturedH.toFixed(2))
              const needed = Number(Math.max(0, targetH - capturedH).toFixed(2))
              const overshoot = Number(Math.max(0, capturedH - targetH).toFixed(2))
              const capturedVis = Number(Math.min(captured, targetH).toFixed(2))
              return {
                filter,
                captured,
                capturedVis,
                needed,
                overshoot,
                target: Number(targetH.toFixed(2)),
              }
            })
            .filter(r => r.captured > 0 || r.needed > 0 || r.overshoot > 0)

          if (rows.length === 0) return null

          return (
            <ChartCard key={target} title={`${target}`}>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows}>
                    <XAxis dataKey="filter" tick={{ fill: colors.axis }} />
                    <YAxis tick={{ fill: colors.axis }} />
                    <Tooltip
                      cursor={{ fill: 'transparent' }}
                      content={({ payload, label, active }: any) => {
                        if (!active || !payload || !payload.length) return null
                        const p = payload[0].payload
                        return (
                          <div style={{ background: '#0F172A', border: '1px solid #1F2937', color: '#F9FAFB', padding: 12 }}>
                            <div style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div>
                            <div style={{ color: '#20c945', marginBottom: 4 }}>Captured (h) : {p.captured?.toFixed(2)} h</div>
                            <div style={{ color: '#4892db', marginBottom: 4 }}>Needed (h) : {p.needed?.toFixed(2)} h</div>
                            <div style={{ color: 'hsla(64, 80%, 43%, 1.00)', marginBottom: 4 }}>Overshoot (h) : {p.overshoot?.toFixed(2)} h</div>
                            <div style={{ color: '#9CA3AF' }}>Target (h) : {p.target?.toFixed(2)} h</div>
                          </div>
                        )
                      }}
                    />
                    <Legend />
                    <Bar dataKey="capturedVis"  stackId="a" name="Captured (h)"  fill={colors.captured} />
                    <Bar dataKey="needed"    stackId="a" name="Needed (h)"    fill={colors.needed} />
                    <Bar dataKey="overshoot" stackId="a" name="Overshoot (h)" fill={colors.overshoot} />
                    {/* target value shown on hover only (removed visual marker) */}
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
