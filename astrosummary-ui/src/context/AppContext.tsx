import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { apiGetSettings, apiSetSettings } from '../lib/api'
import { scanFrames } from '../lib/scan'
import type { LightFrame, Mode } from '../lib/types'

type Ctx = {
  mode: Mode
  setMode: (m: Mode) => void

  // Backend-only scanning
  backendPath: string
  setBackendPath: (s: string) => void
  recurse: boolean
  setRecurse: (v: boolean) => void

  frames: LightFrame[]
  setFrames: (f: LightFrame[]) => void

  desiredHours?: number
  setDesiredHours: (v: number | undefined) => void
  // scanning state
  scanning: boolean
  onScan: () => Promise<void>
  status: string
  needsRescan: boolean
  setNeedsRescan: (v: boolean) => void
  // debug toggle exposed to UI
  debugEnabled: boolean
  setDebugEnabled: (v: boolean) => void
}

const AppContext = createContext<Ctx | undefined>(undefined)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<Mode>('AstroBin Export')
  const [backendPath, setBackendPathState] = useState<string>(() => { try { return localStorage.getItem('backendPath') ?? '' } catch { return '' } })
    const setBackendPath = (s: string) => { setBackendPathState(s); try { localStorage.setItem('backendPath', s) } catch {} ; try { apiSetSettings({ path: s, recurse }) } catch {} ; setNeedsRescan(true) }

  const [recurse, setRecurseState] = useState<boolean>(() => { try { const v = localStorage.getItem('recurse'); return v == null ? true : v === '1' } catch { return true } })
    const setRecurse = (v: boolean) => { setRecurseState(v); try { localStorage.setItem('recurse', v ? '1' : '0') } catch {} ; try { apiSetSettings({ path: backendPath, recurse: v }) } catch {} ; setNeedsRescan(true) }
  const [frames, setFrames] = useState<LightFrame[]>([])
  const [scanning, setScanning] = useState(false)
  const [status, setStatus] = useState('')
  const [needsRescan, setNeedsRescan] = useState(false)
  const [debugEnabledState, setDebugEnabledState] = useState<boolean>(() => { try { return localStorage.getItem('debugEnabled') === '1' } catch { return false } })
  const setDebugEnabled = (v: boolean) => { setDebugEnabledState(v); try { localStorage.setItem('debugEnabled', v ? '1' : '0') } catch {} }
    const [desiredHours, setDesiredHoursState] = useState<number | undefined>(() => {
        try {
          const s = localStorage.getItem('desiredHours')
          if (s == null) return 20
          const n = Number(s)
          return Number.isFinite(n) ? n : 20
        } catch {
          return 20
        }
      })
    const setDesiredHours = (v: number | undefined) => {
      setDesiredHoursState(v)
      try {
        if (typeof v === 'number') localStorage.setItem('desiredHours', String(v))
        else localStorage.removeItem('desiredHours')
      } catch {}
    }

  // load server-side settings on mount
  useEffect(() => {
    let mounted = true
    apiGetSettings().then(s => {
      if (!mounted) return
      try { if (s.path) { setBackendPathState(s.path); localStorage.setItem('backendPath', s.path) } } catch {}
      try { setRecurseState(Boolean(s.recurse)); localStorage.setItem('recurse', s.recurse ? '1' : '0') } catch {}
    }).catch(() => {})
    return () => { mounted = false }
  }, [])

  // shared scan action used by Sidebar (and pages can call it indirectly)
  const onScan = async () => {
    if (!backendPath?.trim()) {
      setStatus('Enter a valid backend path')
      return
    }
  // clear the rescan flag when a scan is triggered
  setNeedsRescan(false)
  setScanning(true)
    try {
      const { frames: lf, info } = await scanFrames({ backendPath, recurse })
      setFrames(lf)
      setStatus(info)
    } catch (err) {
      setStatus('Scan failed')
    } finally {
      setScanning(false)
    }
  }

  const value = useMemo<Ctx>(() => ({
    mode, setMode,
    backendPath: backendPath,
    setBackendPath,
    recurse: recurse,
    setRecurse,
    frames, setFrames,
    desiredHours, setDesiredHours,
    scanning, onScan, status,
    needsRescan, setNeedsRescan,
  debugEnabled: debugEnabledState,
  setDebugEnabled,
  }), [mode, backendPath, recurse, frames, desiredHours, scanning, status])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): Ctx {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
