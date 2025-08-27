import React, { createContext, useContext, useMemo, useState } from 'react'
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
}

const AppContext = createContext<Ctx | undefined>(undefined)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<Mode>('AstroBin Export')
  const [backendPath, setBackendPath] = useState('')
  const [recurse, setRecurse] = useState(true)
  const [frames, setFrames] = useState<LightFrame[]>([])
  const [desiredHours, setDesiredHours] = useState<number | undefined>(undefined)

  const value = useMemo<Ctx>(() => ({
    mode, setMode,
    backendPath, setBackendPath,
    recurse, setRecurse,
    frames, setFrames,
    desiredHours, setDesiredHours,
  }), [mode, backendPath, recurse, frames, desiredHours])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): Ctx {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
