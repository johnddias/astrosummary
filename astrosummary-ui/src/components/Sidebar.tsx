import type { Mode } from '../lib/types'
import { useApp } from '../context/AppContext'
import classNames from 'classnames'

const MODES: Mode[] = ['AstroBin Export', 'Ratio Planner', 'Target Filter Report']

export default function Sidebar() {
  const { mode, setMode, backendPath, setBackendPath, recurse, setRecurse, frames, needsRescan } = useApp()
  const { scanning, onScan } = useApp()
  const { debugEnabled, setDebugEnabled } = useApp()

  return (
    <aside className="w-72 shrink-0 h-screen bg-bg-sidebar border-r border-slate-700 p-4 flex flex-col gap-4">
      <div className="text-xl font-semibold">AstroSummary</div>

      <div className="space-y-2">
        {MODES.map(m => (
          <button
            key={m}
            className={classNames(
              'w-full text-left px-3 py-2 rounded-xl',
              mode === m ? 'bg-slate-700 text-white' : 'text-text-secondary hover:bg-slate-800'
            )}
            onClick={() => setMode(m)}
          >
            {m}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-3">

        <div className="space-y-1">
          <label className="text-sm text-text-secondary">Path to .fits files</label>
          <input
            className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
            placeholder={navigator.platform.startsWith('Win') ? 'Y:\\\\M101' : '/data/M101'}
            value={backendPath}
            onChange={(e) => setBackendPath(e.target.value)}
          />
        </div>

        <div className="flex gap-2 items-center">
          <button
            className="px-3 py-2 rounded-xl bg-accent-primary text-black disabled:opacity-60"
            onClick={onScan}
            disabled={scanning}
          >
            {scanning ? 'Scanning…' : 'Scan'}
          </button>
          {needsRescan && (
            <div className="flex items-center gap-2 text-sm text-red-400">
              <span className="w-2 h-2 rounded-full bg-red-600 inline-block" />
              <span>Rescan required</span>
            </div>
          )}
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={recurse} onChange={(e) => setRecurse(e.target.checked)} />
          Recurse subfolders
        </label>

        <div className="text-xs text-text-secondary">
          Current LIGHT frames: <span className="text-white">{frames.length}</span>
        </div>
      </div>

      <div className="mt-auto text-xs text-text-secondary">
        <div className="flex items-center justify-between">
          <div>Dark theme • Recharts • Backend scan</div>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={debugEnabled} onChange={(e) => setDebugEnabled(e.target.checked)} />
            <span className="text-text-secondary">Debug</span>
          </label>
        </div>
      </div>
    </aside>
  )
}
