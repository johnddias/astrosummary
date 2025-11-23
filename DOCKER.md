# Running AstroSummary in Docker

This project can be run using Docker and Docker Compose.

**For Synology NAS setup, see [SYNOLOGY_SETUP.md](SYNOLOGY_SETUP.md)**

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- At least 2GB of available disk space

## Quick Start

1. **Build and start the containers:**
   ```bash
   docker-compose up --build
   ```

2. **Access the application:**
   - Frontend: http://localhost:3001
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Configuration

### Backend API URL

The frontend is configured to connect to the backend at `http://localhost:8000` by default. If you need to change this, modify the `VITE_API_URL` build argument in `docker-compose.yml`:

```yaml
frontend:
  build:
    args:
      - VITE_API_URL=http://your-backend-url:8000
```

**Note:** After changing the API URL, you'll need to rebuild the frontend:
```bash
docker-compose build frontend
docker-compose up
```

### Data Volumes

The backend needs access to your astrophotography files to scan them. You must mount your Windows directories into the container.

**Important:** When using Docker, you must use the **container path** (not the Windows path) in the UI.

#### Configuring Volume Mounts

1. **Edit `docker-compose.yml`** and add volume mounts under the `backend` service:

```yaml
backend:
  volumes:
    # Mount Windows drive to container path
    - R:/__astrophotography:/data/astrophotography:ro
    # Add more as needed:
    # - Y:/M101:/data/m101:ro
```

2. **Use container paths in the UI:**
   - Windows path: `R:\__astrophotography\Deep Sky\SFRO Data\Sh-2 132 4 Panel`
   - Container path: `/data/astrophotography/Deep Sky/SFRO Data/Sh-2 132 4 Panel`
   
   **Use the container path in the application!**

#### Windows Path Format

On Windows with Docker Desktop, you can mount drives directly:
- `R:/__astrophotography:/data/astrophotography:ro` ✅
- `R:\__astrophotography:/data/astrophotography:ro` ✅ (backslashes work too)

#### Example

If your files are at `R:\__astrophotography\Deep Sky\SFRO Data\Sh-2 132 4 Panel`:

1. Mount it in `docker-compose.yml`:
   ```yaml
   - R:/__astrophotography:/data/astrophotography:ro
   ```

2. In the UI, enter:
   ```
   /data/astrophotography/Deep Sky/SFRO Data/Sh-2 132 4 Panel
   ```

3. Restart the containers:
   ```bash
   docker-compose down
   docker-compose up
   ```

## Development

### Rebuilding after code changes

- **Backend changes:** Restart the backend container:
  ```bash
  docker-compose restart backend
  ```

- **Frontend changes:** Rebuild the frontend:
  ```bash
  docker-compose build frontend
  docker-compose up -d frontend
  ```

### Viewing logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stopping the containers

```bash
docker-compose down
```

### Clean rebuild (removes containers and volumes)

```bash
docker-compose down -v
docker-compose up --build
```

## Services

- **backend**: FastAPI application running on port 8000
- **frontend**: React/Vite application served by nginx on port 3001

## Troubleshooting

### Frontend can't connect to backend

1. Ensure both containers are running: `docker-compose ps`
2. Check backend logs: `docker-compose logs backend`
3. Verify the API URL in the frontend build matches your backend URL
4. If running on a different host, update `VITE_API_URL` and rebuild

### Permission issues with mounted volumes

On Linux, you may need to adjust permissions for mounted directories. The backend runs as the default user in the container.

### Scan not finding files

1. **Check volume mounts:** Ensure your directories are mounted in `docker-compose.yml`
2. **Use container paths:** In the UI, use the container path (e.g., `/data/astrophotography/...`), not the Windows path (e.g., `R:\...`)
3. **Verify mount:** Check if the mount works:
   ```bash
   docker-compose exec backend ls -la /data/astrophotography
   ```
4. **Check path format:** Use forward slashes in container paths: `/data/path/to/files`

### Port conflicts

If ports 3000 or 8000 are already in use, modify the port mappings in `docker-compose.yml`:

```yaml
backend:
  ports:
    - "8001:8000"  # Change 8000 to 8001

frontend:
  ports:
    - "3001:80"  # Change 3000 to 3001
```
