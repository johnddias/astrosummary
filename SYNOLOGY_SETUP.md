# Running AstroSummary on Synology NAS

This guide explains how to set up and run AstroSummary on your Synology NAS using Docker.

## Prerequisites

- Synology NAS with Docker package installed
- SSH access enabled (for command-line setup)
- Your astrophotography files stored on the NAS

## Step 1: Install Docker on Synology

1. Open **Package Center** in DSM
2. Search for **"Docker"**
3. Click **Install**
4. Wait for installation to complete

## Step 2: Prepare Your Files

1. Ensure your astrophotography files are on the NAS
2. Note the path to your files (typically `/volume1/shared_folder_name`)
3. You can find shared folders in **Control Panel** → **Shared Folder**

## Step 3: Upload Project Files

You have two options:

### Option A: Using Git (Recommended)

1. SSH into your Synology NAS:
   ```bash
   ssh admin@your-nas-ip
   ```

2. Navigate to a directory where you want the project:
   ```bash
   cd /volume1/docker
   ```

3. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/astrosummary.git
   cd astrosummary
   ```

### Option B: Using File Station

1. Open **File Station** in DSM
2. Create a folder (e.g., `/docker/astrosummary`)
3. Upload all project files via File Station or SMB/CIFS

## Step 4: Configure Volume Mounts

**Recommended:** Use `docker-compose.override.yml` for environment-specific paths (this file is git-ignored):

1. Copy the example file:
   ```bash
   cp docker-compose.override.yml.example docker-compose.override.yml
   ```

2. Edit `docker-compose.override.yml` and update the path:
   ```yaml
   services:
     backend:
       volumes:
         - /volume1/DiasNAS/astrophotography:/data/astrophotography:ro
   ```

**Alternative:** Edit `docker-compose.yml` directly (but you'll need to do this after each git pull).

**To find your exact path:**
- SSH into the NAS and run: `ls -la /volume1/`
- Or check in DSM: **Control Panel** → **Shared Folder**

## Step 5: Build and Run

### Using Docker Compose (Recommended)

1. SSH into your Synology NAS
2. Navigate to the project directory:
   ```bash
   cd /volume1/docker/astrosummary
   ```

3. Build and start the containers:
   ```bash
   docker-compose up -d --build
   ```

4. Check if containers are running:
   ```bash
   docker-compose ps
   ```

### Using Synology Docker GUI

1. Open **Docker** package in DSM
2. Go to **Container** tab
3. Click **Create** → **From docker-compose.yml**
4. Select your `docker-compose.yml` file
5. Click **Next** and follow the wizard

## Step 6: Access the Application

Once running, access the application:

- **Frontend**: `http://your-nas-ip:3001`
- **Backend API**: `http://your-nas-ip:8000`
- **API Docs**: `http://your-nas-ip:8000/docs`

Replace `your-nas-ip` with your Synology NAS IP address.

## Step 7: Configure Scanning Paths

In the web UI:

1. Open the application at `http://your-nas-ip:3001`
2. In the sidebar, enter the **container path** (not the Synology path):
   - **Container path**: `/data/astrophotography/Deep Sky/SFRO Data/Sh-2 132 4 Panel`
   - **NOT** the Synology path: `/volume1/astrophotography/...`

## Troubleshooting

### Containers won't start

1. Check logs:
   ```bash
   docker-compose logs
   ```

2. Verify volume paths exist:
   ```bash
   ls -la /volume1/astrophotography
   ```

3. Check permissions - the Docker user needs read access to the folders

### Permission Denied Errors

If you get permission errors:

1. SSH into the NAS
2. Check folder permissions:
   ```bash
   ls -la /volume1/astrophotography
   ```

3. Adjust permissions if needed (be careful with this):
   ```bash
   chmod -R 755 /volume1/astrophotography
   ```

### Port Conflicts

If ports 3001 or 8000 are already in use, use `docker-compose.override.yml`:

1. Create or edit `docker-compose.override.yml`:
   ```yaml
   services:
     backend:
       ports:
         - "8001:8000"  # Use port 8001 on host instead of 8000
     
     frontend:
       ports:
         - "3002:80"  # Use port 3002 on host instead of 3001
       build:
         args:
           # Update API URL to match your backend port
           - VITE_API_URL=http://your-nas-ip:8001
   ```

2. Rebuild and restart containers:
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

**Important:** If you change the backend port, you must also update `VITE_API_URL` in the frontend build args and rebuild, since the API URL is baked into the frontend at build time.

### Finding Your Shared Folder Paths

1. **Via SSH:**
   ```bash
   ls -la /volume1/
   ```

2. **Via DSM:**
   - Control Panel → Shared Folder
   - Right-click a folder → Properties
   - Check the "Path" field

3. **Common paths:**
   - `/volume1/photo` - if you have a "photo" shared folder
   - `/volume1/homes` - user home directories
   - `/volume1/docker` - if you created a docker folder

## Updating the Application

1. SSH into the NAS
2. Navigate to the project directory
3. Pull latest changes (if using git):
   ```bash
   git pull
   ```
4. Rebuild and restart:
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

## Stopping the Application

```bash
docker-compose down
```

## Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Security Considerations

- The backend API is exposed on port 8000 - consider using Synology's firewall to restrict access
- Consider setting up a reverse proxy (Synology's built-in reverse proxy or nginx) for HTTPS
- Use read-only mounts (`:ro`) to prevent accidental file modifications

## Performance Tips

- For large directories, scanning may take time - be patient
- Consider mounting only the specific subdirectories you need to scan
- The application uses read-only mounts, so it won't modify your files

