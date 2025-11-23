# Docker Troubleshooting Guide

## Volume Mount Issues on Windows

### Problem: Empty directory in container (`/data/astrophotography` is empty)

This usually means Docker Desktop isn't properly sharing your Windows drive.

### Solution 1: Share the Drive in Docker Desktop

1. Open **Docker Desktop**
2. Go to **Settings** (gear icon)
3. Navigate to **Resources** → **File Sharing**
4. Click **"+"** to add a new path
5. Add `R:\` (or the specific directory `R:\__astrophotography`)
6. Click **"Apply & Restart"**
7. Wait for Docker Desktop to restart
8. Restart your containers:
   ```bash
   docker-compose down
   docker-compose up
   ```

### Solution 2: Try Different Path Formats

If sharing the drive doesn't work, try different path formats in `docker-compose.yml`:

**Format 1 (Forward slashes):**
```yaml
- R:/__astrophotography:/data/astrophotography:ro
```

**Format 2 (Lowercase drive):**
```yaml
- r:/__astrophotography:/data/astrophotography:ro
```

**Format 3 (Escaped backslashes):**
```yaml
- "R:\\__astrophotography:/data/astrophotography:ro"
```

**Format 4 (WSL2 path - if using WSL2 backend):**
```yaml
- /mnt/r/__astrophotography:/data/astrophotography:ro
```

### Solution 3: Verify the Mount

After updating `docker-compose.yml`, verify the mount works:

```bash
# Check if directory exists
docker-compose exec backend ls -la /data/astrophotography

# Should show your files, not be empty
```

### Solution 4: Check Docker Desktop Backend

1. Open Docker Desktop
2. Go to **Settings** → **General**
3. Check if **"Use the WSL 2 based engine"** is enabled
4. If using WSL2, you might need to use WSL2 path format (Format 4 above)

### Solution 5: Use Full UNC Path (Advanced)

If nothing else works, try using the full UNC path:

```yaml
- //?/R:/__astrophotography:/data/astrophotography:ro
```

### Common Issues

**Issue:** "Drive not found" or empty directory
- **Fix:** Ensure the drive is shared in Docker Desktop File Sharing settings

**Issue:** Permission denied
- **Fix:** The volume is mounted as read-only (`:ro`). If you need write access, remove `:ro`

**Issue:** Path with spaces not working
- **Fix:** Try quoting the path: `"R:/__astrophotography/Deep Sky":/data/astrophotography:ro`

### Testing the Mount

Once configured, test it:

```bash
# List contents
docker-compose exec backend ls -la /data/astrophotography

# Check a specific subdirectory
docker-compose exec backend ls -la "/data/astrophotography/Deep Sky"

# If you see your files, the mount is working!
```


