import { useEffect, useRef, useState } from 'react'
import DirectoryBrowser from './DirectoryBrowser'
import { getStickyPath, setStickyPath, clearStickyPath, fetchFileFromPath } from '../lib/stickyFile'

interface StickyFileFieldProps {
  /** Unique key for localStorage persistence, e.g. 'session.nina_log'. */
  storageKey: string
  label: string
  /** File extensions (without the dot) offered by the server-side browser, e.g. ['txt']. */
  fileExtensions: string[]
  /** accept attribute for the plain upload fallback. */
  accept?: string
  onFileChange: (file: File | null) => void
}

export default function StickyFileField({ storageKey, label, fileExtensions, accept, onFileChange }: StickyFileFieldProps) {
  const [fileName, setFileName] = useState<string | null>(null)
  const [remembered, setRemembered] = useState(false)
  const [browsing, setBrowsing] = useState(false)
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  // Keep the latest callback without forcing the mount-only effect below to
  // re-run every render (its identity typically changes on every render).
  const onFileChangeRef = useRef(onFileChange)
  onFileChangeRef.current = onFileChange

  useEffect(() => {
    const storedPath = getStickyPath(storageKey)
    if (!storedPath) return
    setLoading(true)
    fetchFileFromPath(storedPath)
      .then(file => {
        setFileName(file.name)
        setRemembered(true)
        onFileChangeRef.current(file)
      })
      .catch(() => {
        clearStickyPath(storageKey)
        setNotice('Previously selected file is no longer available (moved or deleted). Please choose it again.')
      })
      .finally(() => setLoading(false))
  }, [storageKey])

  async function selectPath(path: string) {
    setBrowsing(false)
    setNotice(null)
    setLoading(true)
    try {
      const file = await fetchFileFromPath(path)
      setStickyPath(storageKey, path)
      setFileName(file.name)
      setRemembered(false)
      onFileChangeRef.current(file)
    } catch (e: any) {
      setNotice(`Could not load file: ${e?.message || e}`)
    } finally {
      setLoading(false)
    }
  }

  function handleUploadFallback(file: File | null) {
    // A directly-uploaded file has no server-side path we can reload later,
    // so it can't be made sticky - just use it for this session.
    clearStickyPath(storageKey)
    setNotice(null)
    setFileName(file?.name ?? null)
    setRemembered(false)
    onFileChangeRef.current(file)
  }

  function clearSelection() {
    clearStickyPath(storageKey)
    setFileName(null)
    setRemembered(false)
    setNotice(null)
    onFileChangeRef.current(null)
  }

  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary mb-1">{label}</label>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="px-2 py-1 text-xs rounded bg-slate-700 hover:bg-slate-600 text-text-primary"
          onClick={() => setBrowsing(b => !b)}
        >
          {browsing ? 'Cancel Browse' : 'Browse…'}
        </button>

        <label className="px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 cursor-pointer text-text-secondary">
          Upload file
          <input
            type="file"
            accept={accept}
            className="hidden"
            onChange={(e) => handleUploadFallback(e.target.files?.[0] || null)}
          />
        </label>

        {fileName && (
          <button
            type="button"
            className="px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 text-text-secondary"
            onClick={clearSelection}
          >
            Clear
          </button>
        )}
      </div>

      {browsing && (
        <div className="mt-2">
          <DirectoryBrowser mode="file" fileExtensions={fileExtensions} onSelect={selectPath} />
        </div>
      )}

      {loading && <div className="mt-1 text-xs text-text-secondary">Loading…</div>}

      {!loading && fileName && (
        <div className="mt-1 text-xs">
          <span className="text-green-400">{fileName}</span>
          {remembered && (
            <span className="ml-2 px-1.5 py-0.5 rounded bg-slate-700 text-text-secondary">Remembered</span>
          )}
        </div>
      )}

      {notice && <div className="mt-1 text-xs text-yellow-400">{notice}</div>}
    </div>
  )
}
