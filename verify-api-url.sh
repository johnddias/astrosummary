#!/bin/bash
# Script to verify the API URL configuration in the built frontend

echo "=== Verifying API URL Configuration ==="
echo ""

# Check if docker-compose.override.yml exists
if [ -f "docker-compose.override.yml" ]; then
    echo "✓ docker-compose.override.yml exists"
    echo "Current VITE_API_URL in override file:"
    grep -A 2 "VITE_API_URL" docker-compose.override.yml
    echo ""
else
    echo "✗ docker-compose.override.yml NOT found"
    echo ""
fi

# Check the built frontend files for the API URL
echo "Checking if frontend container is running..."
CONTAINER_ID=$(docker ps -q -f name=astrosummary-frontend)

if [ -n "$CONTAINER_ID" ]; then
    echo "✓ Frontend container is running (ID: $CONTAINER_ID)"
    echo ""
    echo "Searching for API URL in built JavaScript files..."
    docker exec $CONTAINER_ID sh -c "grep -r 'http.*:800' /usr/share/nginx/html/assets/*.js" 2>/dev/null | head -5
    echo ""
    echo "If you see 'localhost' or '127.0.0.1' above instead of '192.168.4.228:8001',"
    echo "then the VITE_API_URL was NOT picked up during the build."
    echo ""
    echo "Solution: Rebuild the frontend with:"
    echo "  docker-compose build --no-cache frontend"
    echo "  docker-compose up -d frontend"
else
    echo "✗ Frontend container is NOT running"
    echo "Start it with: docker-compose up -d"
fi

echo ""
echo "=== End Verification ==="
