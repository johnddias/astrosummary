import { useMemo, useState, useEffect } from 'react'
import { useApp } from '../context/AppContext'
import { totalsByTarget, computeEqualGoal } from '../library/analysis'
import ChartCard from '../components/ChartCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { normalizeFilter } from '../library/filters'
import TargetFilterReport from './TargetFilterReport'
export default function RatioPlanner() {
  const { frames, desiredHours, setDesiredHours, debugEnabled, scanning } = useApp()
  // per-filter ratio inputs (defaults to 1.0) - initialized from localStorage when possible
  const [haRatio, setHaRatio] = useState<number>(() => {
    try { const v = parseFloat(localStorage.getItem('ratio.ha') ?? ''); return isNaN(v) ? 1.0 : Math.round(v*10)/10 } catch { return 1.0 }
  })
  const [oiiiRatio, setOiiiRatio] = useState<number>(() => {
    try { const v = parseFloat(localStorage.getItem('ratio.oiii') ?? ''); return isNaN(v) ? 1.0 : Math.round(v*10)/10 } catch { return 1.0 }
  })
  const [siiRatio, setSiiRatio] = useState<number>(() => {
    try { const v = parseFloat(localStorage.getItem('ratio.sii') ?? ''); return isNaN(v) ? 1.0 : Math.round(v*10)/10 } catch { return 1.0 }
  })
  const [rRatio, setRRatio] = useState<number>(() => {
    try { const v = parseFloat(localStorage.getItem('ratio.r') ?? ''); return isNaN(v) ? 1.0 : Math.round(v*10)/10 } catch { return 1.0 }
  })
  const [gRatio, setGRatio] = useState<number>(() => {
    try { const v = parseFloat(localStorage.getItem('ratio.g') ?? ''); return isNaN(v) ? 1.0 : Math.round(v*10)/10 } catch { return 1.0 }
  })
  const [bRatio, setBRatio] = useState<number>(() => {
    try { const v = parseFloat(localStorage.getItem('ratio.b') ?? ''); return isNaN(v) ? 1.0 : Math.round(v*10)/10 } catch { return 1.0 }
  })
  const [lRatio, setLRatio] = useState<number>(() => {
    try { const v = parseFloat(localStorage.getItem('ratio.l') ?? ''); return isNaN(v) ? 1.0 : Math.round(v*10)/10 } catch { return 1.0 }
  })
  const { colors } = useApp()
  const [subframeMinutes, setSubframeMinutes] = useState<number>(() => {
    try { const v = Number(localStorage.getItem('subframeMinutes')); return Number.isFinite(v) && v > 0 ? v : 5 } catch { return 5 }
  })
  const [filterMode, setFilterMode] = useState<'narrowband'|'broadband'>(() => {
    try { return (localStorage.getItem('filterMode') as any) || 'narrowband' } catch { return 'narrowband' }
  })

  // colors is provided by AppContext (chosen from Sidebar)

  useEffect(() => { try { localStorage.setItem('subframeMinutes', String(subframeMinutes)) } catch {} }, [subframeMinutes])

  // persist filter mode and ratios
  useEffect(() => {
    try {
      localStorage.setItem('filterMode', filterMode)
      localStorage.setItem('ratio.ha', haRatio.toFixed(1))
      localStorage.setItem('ratio.oiii', oiiiRatio.toFixed(1))
      localStorage.setItem('ratio.sii', siiRatio.toFixed(1))
      localStorage.setItem('ratio.r', rRatio.toFixed(1))
      localStorage.setItem('ratio.g', gRatio.toFixed(1))
      localStorage.setItem('ratio.b', bRatio.toFixed(1))
      localStorage.setItem('ratio.l', lRatio.toFixed(1))
    } catch {}
  }, [filterMode, haRatio, oiiiRatio, siiRatio, rRatio, gRatio, bRatio, lRatio])

  // colors comes from context

  const framesForDisplay = scanning ? [] : frames

  const goal = useMemo(() => {
    // Always use explicit per-filter inputs as the goal weights
    const out: Record<string, number> = {}
    out['Ha'] = haRatio || 1.0
    out['OIII'] = oiiiRatio || 1.0
    out['SII'] = siiRatio || 1.0
    out['R'] = rRatio || 1.0
    out['G'] = gRatio || 1.0
    out['B'] = bRatio || 1.0
    out['L'] = lRatio || 1.0
  // if user hasn't provided any non-zero weights, fallback to equal goal behavior
  const sumWeights = Object.values(out).reduce((a, b) => a + (b || 0), 0)
  if (sumWeights === 0) return computeEqualGoal(framesForDisplay)
    return out
  }, [frames, haRatio, oiiiRatio, siiRatio, rRatio, gRatio, bRatio, lRatio])

  const totals = useMemo(() => totalsByTarget(framesForDisplay), [framesForDisplay])
  const targets = useMemo(() => Object.keys(totals).sort(), [totals])

  const multipleTargets = targets.length > 1

  return (
    <div className="space-y-4">
  <div className="flex flex-wrap items-start gap-3">

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
          <label className="text-xs text-text-secondary">Subframe length (minutes)</label>
          <input
            type="number"
            step="1"
            min="1"
            className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
            value={subframeMinutes}
            onChange={(e) => setSubframeMinutes(Number(e.target.value || 1))}
          />
        </div>

        <div className="flex flex-col">
          <label className="flex items-center gap-2 text-lg text-text-secondary">
            <input type="radio" name="filterMode" checked={filterMode === 'narrowband'} onChange={() => setFilterMode('narrowband')} className="w-5 h-5" />
            <span>Narrowband</span>
          </label>
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-4">
              <div className="text-xs text-text-secondary">Ha</div>
              <input className="w-28 px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-center" type="number" step="0.1" min="1.0" max="9.9" value={haRatio.toFixed(1)} onChange={(e) => { const v = Math.max(1.0, Math.min(9.9, Number(parseFloat(e.target.value || '1')))); setHaRatio(Math.round(v*10)/10) }} />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="text-xs text-text-secondary">OIII</div>
              <input className="w-28 px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-center" type="number" step="0.1" min="1.0" max="9.9" value={oiiiRatio.toFixed(1)} onChange={(e) => { const v = Math.max(1.0, Math.min(9.9, Number(parseFloat(e.target.value || '1')))); setOiiiRatio(Math.round(v*10)/10) }} />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="text-xs text-text-secondary">SII</div>
              <input className="w-28 px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-center" type="number" step="0.1" min="1.0" max="9.9" value={siiRatio.toFixed(1)} onChange={(e) => { const v = Math.max(1.0, Math.min(9.9, Number(parseFloat(e.target.value || '1')))); setSiiRatio(Math.round(v*10)/10) }} />
            </div>
          </div>
        </div>

        <div className="flex flex-col">
          <label className="flex items-center gap-2 text-lg text-text-secondary">
            <input type="radio" name="filterMode" checked={filterMode === 'broadband'} onChange={() => setFilterMode('broadband')} className="w-5 h-5" />
            <span>Broadband</span>
          </label>
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-4">
              <div className="text-xs text-text-secondary">R</div>
              <input className="w-28 px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-center" type="number" step="0.1" min="1.0" max="9.9" value={rRatio.toFixed(1)} onChange={(e) => { const v = Math.max(1.0, Math.min(9.9, Number(parseFloat(e.target.value || '1')))); setRRatio(Math.round(v*10)/10) }} />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="text-xs text-text-secondary">G</div>
              <input className="w-28 px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-center" type="number" step="0.1" min="1.0" max="9.9" value={gRatio.toFixed(1)} onChange={(e) => { const v = Math.max(1.0, Math.min(9.9, Number(parseFloat(e.target.value || '1')))); setGRatio(Math.round(v*10)/10) }} />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="text-xs text-text-secondary">B</div>
              <input className="w-28 px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-center" type="number" step="0.1" min="1.0" max="9.9" value={bRatio.toFixed(1)} onChange={(e) => { const v = Math.max(1.0, Math.min(9.9, Number(parseFloat(e.target.value || '1')))); setBRatio(Math.round(v*10)/10) }} />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="text-xs text-text-secondary">L</div>
              <input className="w-28 px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-center" type="number" step="0.1" min="1.0" max="9.9" value={lRatio.toFixed(1)} onChange={(e) => { const v = Math.max(1.0, Math.min(9.9, Number(parseFloat(e.target.value || '1')))); setLRatio(Math.round(v*10)/10) }} />
            </div>
          </div>
        </div>

  {/* custom ratios removed - using explicit per-filter inputs instead */}
        

      </div>

  {/* Scanning moved to Sidebar; status is available in AppContext if needed */}

      {targets.length === 0 && (
        <div className="text-text-secondary">No LIGHT frames yet — run Scan from the sidebar.</div>
      )}

      {/* show the total-hours-by-filter summary only when more than one target exists */}
      {multipleTargets && (
        <div className="flex justify-center">
          <div className="w-full max-w-3xl">
            <TargetFilterReport />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {targets.map(target => {
          const current = totals[target] || {}
          // Build normalized goal weights and compute totalSeconds for target calculation
          const normGoal: Record<string, number> = {}
          for (const [raw, w] of Object.entries(goal)) {
            const k = normalizeFilter(raw)
            normGoal[k] = (normGoal[k] || 0) + (w || 0)
          }
          const totalSeconds = (desiredHours && desiredHours > 0)
            ? desiredHours * 3600
            : Object.values(current).reduce((a, b) => a + (b || 0), 0)

          const unionKeys = Object.keys({ ...current, ...goal }).sort()
          const narrow = ['Ha', 'OIII', 'SII']
          const broad = ['R', 'G', 'B', 'L']
          const displayedKeys = unionKeys.filter(k => {
            if (narrow.includes(k) && filterMode === 'narrowband') return true
            if (broad.includes(k) && filterMode === 'broadband') return true
            return false
          })

          // sum weights only for displayed filters
          const sumW = displayedKeys.reduce((s, k) => s + (normGoal[k] || 0), 0)

          const rows = displayedKeys
            .map(filter => {
              const capturedH = (current[filter] || 0) / 3600
              // compute this filter's target hours from normalized goal weights
              const weight = normGoal[filter] || 0
              // if sumW is zero (no weights for displayed filters), distribute equally
              const targetSec = sumW > 0 ? (weight / sumW) * totalSeconds : (displayedKeys.length > 0 ? (totalSeconds / displayedKeys.length) : 0)
              const targetH = targetSec / 3600
              const captured = Number(capturedH.toFixed(2))
              const needed = Number(Math.max(0, targetH - capturedH).toFixed(2))
              const overshoot = Number(Math.max(0, capturedH - targetH).toFixed(2))
              const capturedVis = Number(Math.min(captured, targetH).toFixed(2))
              const subsNeeded = Math.ceil((needed * 60) / subframeMinutes)
              return {
                filter,
                captured,
                capturedVis,
                needed,
                subsNeeded,
                overshoot,
                target: Number(targetH.toFixed(2)),
              }
            })
            .filter(r => r.captured > 0 || r.needed > 0 || r.overshoot > 0)
            .filter(r => {
              const narrow = ['Ha', 'OIII', 'SII']
              const broad = ['R', 'G', 'B', 'L']
              // include if either set is selected and the filter belongs to that set
              if (narrow.includes(r.filter) && filterMode === 'narrowband') return true
              if (broad.includes(r.filter) && filterMode === 'broadband') return true
              return false
            })

          if (rows.length === 0) return null

          // build debug info for displayed filters
          const debug = displayedKeys.map(k => {
            const weight = normGoal[k] || 0
            const targetSec = sumW > 0 ? (weight / sumW) * totalSeconds : (displayedKeys.length > 0 ? (totalSeconds / displayedKeys.length) : 0)
            return {
              filter: k,
              weight,
              targetHours: Number((targetSec / 3600).toFixed(4)),
              capturedHours: Number(((current[k] || 0) / 3600).toFixed(4))
            }
          })

          return (
            <ChartCard key={target} title={`${target}`}>
              {debugEnabled && (
                <div className="mb-2 p-2 rounded bg-slate-900 border border-slate-800 text-xs">
                  <div className="font-semibold">Debug</div>
                  <div>Displayed filters: {displayedKeys.join(', ') || 'none'}</div>
                  <div>sumW (weights sum): {sumW.toFixed(2)}</div>
                  <div className="mt-1">Per-filter details:</div>
                  <pre className="whitespace-pre-wrap">{JSON.stringify(debug, null, 2)}</pre>
                </div>
              )}

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
                        const fmt = (v: number|undefined) => {
                          if (typeof v !== 'number' || !isFinite(v)) return '0:00'
                          const totalMinutes = Math.round(v * 60)
                          const hrs = Math.floor(totalMinutes / 60)
                          const mins = totalMinutes % 60
                          return `${hrs}:${String(mins).padStart(2, '0')}`
                        }
                        return (
                          <div style={{ background: '#0F172A', border: '1px solid #1F2937', color: '#F9FAFB', padding: 12 }}>
                            <div style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div>
                            <div style={{ color: '#20c945', marginBottom: 4 }}>Captured : {fmt(p.captured)}</div>
                            <div style={{ color: '#4892db', marginBottom: 4 }}>Needed : {fmt(p.needed)}</div>
                              <div style={{ color: 'hsla(64, 80%, 43%, 1.00)', marginBottom: 4 }}>Overshoot : {fmt(p.overshoot)}</div>
                              <div style={{ color: '#F59E0B', marginBottom: 4 }}>Subs needed (@{subframeMinutes}m): {p.subsNeeded ?? 0}</div>
                            <div style={{ color: '#9CA3AF' }}>Target : {fmt(p.target)}</div>
                          </div>
                        )
                      }}
                    />
                    <Legend />
                    <Bar dataKey="capturedVis"  stackId="a" name="Captured"  fill={colors.captured} />
                    <Bar dataKey="needed"    stackId="a" name="Needed"    fill={colors.needed} />
                    <Bar dataKey="overshoot" stackId="a" name="Overshoot" fill={colors.overshoot} />
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
