import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { apiGetSettings, apiSetSettings } from '../library/api'
import { scanFrames } from '../library/scan'
import { normalizeFilter } from '../library/filters'
import type { LightFrame, Mode } from '../library/types'

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
  scanProgress: { files_scanned: number; files_matched: number; total_files?: number }
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
  const [scanProgress, setScanProgress] = useState<{ files_scanned: number; files_matched: number; total_files?: number }>({ files_scanned: 0, files_matched: 0 })
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
  setFrames([])
      const live: LightFrame[] = []
      const { frames: final, info } = await scanFrames({ backendPath, recurse }, (p) => {
        try {
          // update structured progress state
          setScanProgress({ files_scanned: p.files_scanned ?? 0, files_matched: p.files_matched ?? 0, total_files: p.total_files })
          // Show only the scanned / total progress live; omit the matched count until the scan completes
          if (typeof p.total_files === 'number') {
            setStatus(`Scanning: ${p.files_scanned} / ${p.total_files} files scanned`)
          } else {
            setStatus(`Scanning: ${p.files_scanned} files scanned`)
          }
        } catch {}
      }, (f) => {
        // Append normalized frame as it arrives so Sidebar shows live count
        const nf: LightFrame = {
          ...f,
          filter: normalizeFilter((f.filter as any) ?? ''),
          exposure_s: typeof f.exposure_s === 'number' ? f.exposure_s : Number(f.exposure_s) || 0,
          frameType: (f.frameType as any) || 'LIGHT',
        }
  live.push(nf)
  setFrames((prev) => [...prev, nf])
      })

      // final normalization (in case any frames arrived in the final batch)
      const normalized = (final || []).map(f => ({
        ...f,
        filter: normalizeFilter((f.filter as any) ?? ''),
        exposure_s: typeof f.exposure_s === 'number' ? f.exposure_s : Number(f.exposure_s) || 0,
        frameType: (f.frameType as any) || 'LIGHT',
      }))
      // prefer the live-accumulated frames if present, otherwise set final
      if (live.length === 0) setFrames(normalized)
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
    scanProgress,
    needsRescan, setNeedsRescan,
  debugEnabled: debugEnabledState,
  setDebugEnabled,
  }), [mode, backendPath, recurse, frames, desiredHours, scanning, status, needsRescan, debugEnabledState, scanProgress])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): Ctx {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
