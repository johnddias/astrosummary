// Helpers for "sticky" file selections: remembering which server-side file a
// field last pointed to (by absolute path) so it can be reloaded automatically
// on the next visit, mirroring the existing backendPath persistence pattern
// used for FITS directory scanning.
import { API_URL } from './apiConfig'

const STORAGE_PREFIX = 'stickyFile.'

export function getStickyPath(key: string): string | null {
  try {
    return localStorage.getItem(STORAGE_PREFIX + key)
  } catch {
    return null
  }
}

export function setStickyPath(key: string, path: string): void {
  try {
    localStorage.setItem(STORAGE_PREFIX + key, path)
  } catch {
    // localStorage unavailable (private browsing, quota, etc.) - selection
    // just won't survive a refresh.
  }
}

export function clearStickyPath(key: string): void {
  try {
    localStorage.removeItem(STORAGE_PREFIX + key)
  } catch {
    // ignore
  }
}

/**
 * Fetch a file's content from the backend (by absolute path, restricted to
 * DATA_ROOT server-side) and wrap it as a File so it can be handed to the
 * same upload code paths as a browser-picked file.
 */
export async function fetchFileFromPath(path: string): Promise<File> {
  const res = await fetch(`${API_URL}/read_file?path=${encodeURIComponent(path)}`)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `HTTP ${res.status}`)
  }
  const data: { path: string; name: string; content: string; size: number; modified: number } = await res.json()
  const lastModified = data.modified ? Math.round(data.modified * 1000) : Date.now()
  return new File([data.content], data.name, { type: 'text/plain', lastModified })
}
