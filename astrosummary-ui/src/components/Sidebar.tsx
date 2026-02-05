import type { Mode } from '../library/types'
import { useApp } from '../context/AppContext'
import classNames from 'classnames'

const MODES: Mode[] = ['Target Data Visualizer', 'AstroBin Export', 'Session Analyzer', 'NINA Analyzer', 'PHD2 Analyzer', 'Rejection Validation']

export default function Sidebar() {
  const { mode, setMode, debugEnabled, setDebugEnabled, colorScheme, setColorScheme } = useApp()

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
        <div>
          <label className="text-sm text-text-secondary">Chart color scheme</label>
          <select className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 mt-1" value={colorScheme} onChange={(e) => setColorScheme(e.target.value)}>
            <option value="muted">Muted (default)</option>
            <option value="highContrast">High contrast</option>
            <option value="colorBlind">Color-blind friendly</option>
          </select>
        </div>
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
