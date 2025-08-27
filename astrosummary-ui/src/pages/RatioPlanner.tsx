import { useMemo, useState } from 'react'
import { useApp } from '../context/AppContext'
import { scanFrames } from '../lib/scan'
import { totalsByTarget, computeEqualGoal, planToTotalHours, balanceDeficits } from '../lib/analysis'
import ChartCard from '../components/ChartCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { PRESETS } from '../lib/presets'

type RatioSource = 'Equal' | 'Preset' | 'Custom'

export default function RatioPlanner() {
  const { frames, setFrames, desiredHours, setDesiredHours, recurse, backendPath } = useApp()
  const [ratioSource, setRatioSource] = useState<RatioSource>('Equal')
  const [presetName, setPresetName] = useState<string>(Object.keys(PRESETS)[0])
  const [customText, setCustomText] = useState<string>('')
  const [status, setStatus] = useState<string>('')
  const [scanning, setScanning] = useState<boolean>(false)

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

  const goal = useMemo(() => {
    if (ratioSource === 'Preset') return PRESETS[presetName]
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
  }, [ratioSource, presetName, customText, frames])

  const totals = useMemo(() => totalsByTarget(frames), [frames])
  const targets = useMemo(() => Object.keys(totals).sort(), [totals])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <button
          className="px-3 py-2 rounded-xl bg-accent-primary text-black disabled:opacity-60"
          onClick={onScan}
          disabled={scanning}
        >
          {scanning ? 'Scanning…' : 'Scan'}
        </button>

        <div className="flex flex-col">
          <label className="text-xs text-text-secondary">Desired total hours (optional)</label>
          <input
            type="number"
            step="0.5"
            className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
            placeholder="e.g. 40"
            value={desiredHours ?? ''}
            onChange={(e) => setDesiredHours(e.target.value ? Number(e.target.value) : undefined)}
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
            <option>Preset</option>
            <option>Custom</option>
          </select>
        </div>

        {ratioSource === 'Preset' && (
          <div className="flex flex-col">
            <label className="text-xs text-text-secondary">Preset</label>
            <select
              className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
            >
              {Object.keys(PRESETS).map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
        )}

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

      {scanning && (
        <div className="mt-1 h-1 bg-slate-700 rounded overflow-hidden">
          <div className="animate-pulse bg-accent-primary h-1 w-full"></div>
        </div>
      )}

      <div className="text-xs text-text-secondary">{status}</div>

      {targets.length === 0 && !scanning && (
        <div className="text-text-secondary">No LIGHT frames yet — enter a backend path and click Scan.</div>
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
                    <XAxis dataKey="filter" tick={{ fill: '#9CA3AF' }} />
                    <YAxis tick={{ fill: '#9CA3AF' }} />
                    <Tooltip
                      contentStyle={{ background: '#0F172A', border: '1px solid #1F2937', color: '#F9FAFB' }}
                      formatter={(val: any, name: any) => [`${Number(val).toFixed(2)} h`, name]}
                    />
                    <Legend />
                    <Bar dataKey="captured"  stackId="a" name="Captured (h)"  fill="#FFD700" />
                    <Bar dataKey="needed"    stackId="a" name="Needed (h)"    fill="#1E90FF" />
                    <Bar dataKey="overshoot" stackId="a" name="Overshoot (h)" fill="#A9A9A9" />
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
