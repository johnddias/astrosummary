import type { Mode } from '../library/types'
import { useApp } from '../context/AppContext'
import classNames from 'classnames'

const MODES: Mode[] = ['Target Data Visualizer', 'AstroBin Export', 'NINA Analyzer', 'PHD2 Analyzer', 'Rejection Validation']

export default function Sidebar() {
  const { mode, setMode, backendPath, setBackendPath, recurse, setRecurse, frames, needsRescan, scanProgress, status, scanning, onScan, debugEnabled, setDebugEnabled, colorScheme, setColorScheme } = useApp()

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
          <label className="text-sm text-text-secondary flex items-center gap-1">
            Path to .fits files
            <span
              className="cursor-help text-blue-400 hover:text-blue-300"
              title="Docker users: Use Linux container paths with forward slashes.&#10;Example: /data/astrophotography/Deep Sky/Target Name&#10;&#10;The path should match your container mount point, NOT your Windows path.&#10;Spaces in paths are OK - no escaping needed."
            >
              ⓘ
            </span>
          </label>
          <input
            className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700"
            placeholder={navigator.platform.startsWith('Win') ? '/data/astrophotography/Target Name' : '/data/astrophotography/Target Name'}
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

        <div>
          <label className="text-sm text-text-secondary">Chart color scheme</label>
          <select className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 mt-1" value={colorScheme} onChange={(e) => setColorScheme(e.target.value)}>
            <option value="muted">Muted (default)</option>
            <option value="highContrast">High contrast</option>
            <option value="colorBlind">Color-blind friendly</option>
          </select>
        </div>

        <div className="text-xs text-text-secondary">
          Current LIGHT frames: <span className="text-white">{frames.length}</span>
        </div>

        {scanning && (
          <div className="mt-2">
            <div className="text-xs text-text-secondary mb-1">{status}</div>
            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className="h-2 bg-accent-primary"
                style={{ width: scanProgress.total_files ? `${Math.round((scanProgress.files_scanned / scanProgress.total_files) * 100)}%` : `${Math.min(100, scanProgress.files_scanned * 2)}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="mt-auto text-xs text-text-secondary">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={debugEnabled} onChange={(e) => setDebugEnabled(e.target.checked)} />
            <span className="text-text-secondary">Debug</span>
          </label>
        </div>
    </aside>
  )
}
