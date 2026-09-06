import { useState, useEffect } from 'react'
import { API_URL } from '../lib/apiConfig'

interface DirectoryEntry {
  name: string
  path: string
  type: 'directory' | 'file'
  children_count?: number
  size?: number
}

interface BrowseResponse {
  path: string
  parent: string | null
  entries: DirectoryEntry[]
}

interface DirectoryBrowserProps {
  onSelect: (path: string) => void
  initialPath?: string
  /**
   * 'folder' (default): browse to and select a directory (used for FITS scanning).
   * 'file': browse into directories and select an individual file matching `fileExtensions`.
   */
  mode?: 'folder' | 'file'
  /** File extensions (without the dot) to list when mode='file', e.g. ['txt']. */
  fileExtensions?: string[]
}

export default function DirectoryBrowser({ onSelect, initialPath = '', mode = 'folder', fileExtensions }: DirectoryBrowserProps) {
  const [currentPath, setCurrentPath] = useState(initialPath)
  const [rootPath, setRootPath] = useState('')
  const [entries, setEntries] = useState<DirectoryEntry[]>([])
  const [parentPath, setParentPath] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(true)

  useEffect(() => {
    loadDirectory(currentPath)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPath])

  async function loadDirectory(path: string) {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (path) params.set('path', path)
      if (mode === 'file' && fileExtensions && fileExtensions.length > 0) {
        params.set('extensions', fileExtensions.join(','))
      }
      const qs = params.toString()
      const url = qs ? `${API_URL}/browse?${qs}` : `${API_URL}/browse`
      const res = await fetch(url)
      if (!res.ok) {
        // If a saved path is invalid (e.g. Windows path in Docker), fall back to server default
        if (path && (res.status === 403 || res.status === 404)) {
          setCurrentPath('')
          return
        }
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const data: BrowseResponse = await res.json()
      setEntries(data.entries)
      setParentPath(data.parent)
      // Track the current path returned by the backend (handles default root)
      if ((!currentPath || currentPath !== data.path) && !path) {
        setCurrentPath(data.path)
      }
      if (!rootPath && !data.parent) {
        setRootPath(data.path)
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load directory')
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  function handleNavigate(path: string) {
    setCurrentPath(path)
  }

  function handleSelect(path: string) {
    onSelect(path)
  }

  const directories = entries.filter(e => e.type === 'directory')
  const files = entries.filter(e => e.type === 'file')

  return (
    <div className="border border-slate-700 rounded-xl bg-slate-900 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 bg-slate-800 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-text-secondary">{expanded ? '▼' : '▶'}</span>
          <span className="text-sm font-medium">Browse {rootPath || currentPath}</span>
        </div>
        {!expanded && currentPath !== rootPath && (
          <span className="text-xs text-text-secondary truncate max-w-[200px]">{currentPath}</span>
        )}
      </div>

      {expanded && (
        <div className="p-3">
          {/* Current path breadcrumb */}
          <div className="flex items-center gap-2 mb-3 text-sm">
            <span className="text-text-secondary">Path:</span>
            <span className="text-blue-400 font-mono text-xs bg-slate-800 px-2 py-1 rounded">
              {currentPath}
            </span>
            {mode === 'folder' && (
              <button
                onClick={() => handleSelect(currentPath)}
                className="ml-auto px-3 py-1 text-xs bg-accent-primary text-black rounded font-medium hover:bg-green-400"
              >
                Select This Folder
              </button>
            )}
          </div>

          {/* Navigation */}
          {parentPath && (
            <button
              onClick={() => handleNavigate(parentPath)}
              className="flex items-center gap-2 w-full text-left px-3 py-2 rounded hover:bg-slate-800 text-text-secondary mb-2"
            >
              <span>⬆</span>
              <span className="text-sm">.. (go up)</span>
            </button>
          )}

          {loading && (
            <div className="text-text-secondary text-sm py-4 text-center">Loading...</div>
          )}

          {error && (
            <div className="text-red-400 text-sm py-2">{error}</div>
          )}

          {!loading && !error && (
            <div className="max-h-64 overflow-y-auto space-y-1">
              {/* Directories */}
              {directories.map(entry => (
                <div
                  key={entry.path}
                  className="flex items-center gap-2 px-3 py-2 rounded hover:bg-slate-800 cursor-pointer group"
                  onClick={() => handleNavigate(entry.path)}
                >
                  <span className="text-yellow-400">📁</span>
                  <span className="flex-1 text-sm truncate">{entry.name}</span>
                  {entry.children_count !== undefined && entry.children_count > 0 && (
                    <span className="text-xs text-text-secondary">
                      {entry.children_count} items
                    </span>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleSelect(entry.path)
                    }}
                    className="opacity-0 group-hover:opacity-100 px-2 py-0.5 text-xs bg-slate-700 hover:bg-slate-600 rounded"
                  >
                    Select
                  </button>
                </div>
              ))}

              {/* Selectable files (mode='file') */}
              {mode === 'file' && files.length > 0 && (
                <div className="mt-1 pt-1 border-t border-slate-700">
                  {files.map(entry => (
                    <div
                      key={entry.path}
                      className="flex items-center gap-2 px-3 py-2 rounded hover:bg-slate-800 cursor-pointer group"
                      onClick={() => handleSelect(entry.path)}
                    >
                      <span className="text-blue-400">📄</span>
                      <span className="flex-1 text-sm truncate">{entry.name}</span>
                      {entry.size !== undefined && (
                        <span className="text-xs text-text-secondary">
                          {(entry.size / 1024).toFixed(1)} KB
                        </span>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleSelect(entry.path)
                        }}
                        className="opacity-0 group-hover:opacity-100 px-2 py-0.5 text-xs bg-slate-700 hover:bg-slate-600 rounded"
                      >
                        Select
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* FITS files summary (mode='folder') */}
              {mode === 'folder' && files.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-700">
                  <div className="text-xs text-text-secondary px-3 py-1">
                    {files.length} FITS file{files.length !== 1 ? 's' : ''} in this directory
                  </div>
                </div>
              )}

              {directories.length === 0 && files.length === 0 && (
                <div className="text-text-secondary text-sm py-4 text-center">
                  Empty directory
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
