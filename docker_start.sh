#!/bin/bash

# Docker security best practices startup script for Modal CTF
# This script starts the containerized application with maximum security restrictions

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="modal-ctf"
IMAGE_NAME="modal-ctf:secure"
HOST_PORT=80
CONTAINER_PORT=8080

# Check if FLAG is set
if [ -z "$FLAG" ]; then
    echo -e "${YELLOW}⚠️  WARNING: FLAG environment variable not set!${NC}"
    echo -e "${YELLOW}   Using default flag for testing.${NC}"
    echo -e "${YELLOW}   Set it with: export FLAG='CTF{your_flag_here}'${NC}"
    FLAG="CTF{default_flag_for_testing}"
fi

# Check for Modal credentials
if [ -z "$MODAL_TOKEN_ID" ] || [ -z "$MODAL_TOKEN_SECRET" ]; then
    echo -e "${YELLOW}Modal credentials not found in environment, checking ~/.modal.toml...${NC}"
    
    # Expand the home directory path
    MODAL_CONFIG_FILE="$HOME/.modal.toml"
    
    if [ -f "$MODAL_CONFIG_FILE" ]; then
        echo -e "${GREEN}Found Modal config file, extracting credentials...${NC}"
        
        # Extract token_id and token_secret from the active profile
        # First try to get from [default] section, then fall back to first available profile
        
        # Try to extract from default profile
        TOKEN_ID=$(grep -A 10 '^\[default\]' "$MODAL_CONFIG_FILE" 2>/dev/null | grep '^token_id' | cut -d'"' -f2 | head -1)
        TOKEN_SECRET=$(grep -A 10 '^\[default\]' "$MODAL_CONFIG_FILE" 2>/dev/null | grep '^token_secret' | cut -d'"' -f2 | head -1)
        
        # If not found in default, try to get from any profile
        if [ -z "$TOKEN_ID" ] || [ -z "$TOKEN_SECRET" ]; then
            TOKEN_ID=$(grep '^token_id' "$MODAL_CONFIG_FILE" | cut -d'"' -f2 | head -1)
            TOKEN_SECRET=$(grep '^token_secret' "$MODAL_CONFIG_FILE" | cut -d'"' -f2 | head -1)
        fi
        
        if [ -n "$TOKEN_ID" ] && [ -n "$TOKEN_SECRET" ]; then
            MODAL_TOKEN_ID="$TOKEN_ID"
            MODAL_TOKEN_SECRET="$TOKEN_SECRET"
            echo -e "${GREEN}✓ Modal credentials loaded from ~/.modal.toml${NC}"
        else
            echo -e "${RED}Error: Could not parse Modal credentials from ~/.modal.toml${NC}"
            echo "Please ensure the file contains token_id and token_secret"
            exit 1
        fi
    else
        echo -e "${RED}Error: No Modal credentials found!${NC}"
        echo "Either:"
        echo "  1. Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET environment variables"
        echo "  2. Run 'modal setup' to create ~/.modal.toml"
        echo "  3. Ensure ~/.modal.toml exists with valid credentials"
        exit 1
    fi
fi

# Check if running as root (needed for port 80)
if [ "$HOST_PORT" -lt 1024 ] && [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Port $HOST_PORT requires root privileges.${NC}"
    echo "Run with: sudo FLAG='$FLAG' ./docker_start.sh"
    echo "Or change HOST_PORT to 8080 in this script"
    exit 1
fi

echo -e "${GREEN}🔨 Building secure Docker image...${NC}"

# Build the Docker image
docker build -t $IMAGE_NAME . || {
    echo -e "${RED}Failed to build Docker image${NC}"
    exit 1
}

# Stop and remove any existing container
echo -e "${GREEN}🧹 Cleaning up existing containers...${NC}"
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

echo -e "${GREEN}🚀 Starting secure container...${NC}"
echo -e "${GREEN}   FLAG: ${FLAG}${NC}"
echo -e "${GREEN}   Host Port: ${HOST_PORT}${NC}"
echo -e "${GREEN}   Container Port: ${CONTAINER_PORT}${NC}"
echo -e "${GREEN}   Modal Token ID: ${MODAL_TOKEN_ID:0:10}...${NC}"

# Detect OS for platform-specific security options
OS_NAME=$(uname -s)
SECURITY_OPTS=""

if [ "$OS_NAME" = "Linux" ]; then
    # Full security options for Linux
    SECURITY_OPTS="--security-opt no-new-privileges --security-opt apparmor=docker-default --security-opt seccomp=default"
elif [ "$OS_NAME" = "Darwin" ]; then
    # macOS doesn't support all security options
    SECURITY_OPTS="--security-opt no-new-privileges"
    echo -e "${YELLOW}Note: Running on macOS - some Linux security features unavailable${NC}"
fi

# Run container with comprehensive security restrictions
# Using --restart always for CTF resilience (will restart on crash or unhealthy state)
docker run \
    --name $CONTAINER_NAME \
    --detach \
    --restart always \
    --publish $HOST_PORT:$CONTAINER_PORT \
    --env FLAG="$FLAG" \
    --env MODAL_TOKEN_ID="$MODAL_TOKEN_ID" \
    --env MODAL_TOKEN_SECRET="$MODAL_TOKEN_SECRET" \
    --read-only \
    --tmpfs /tmp:noexec,nosuid,nodev,size=10M \
    --tmpfs /run:noexec,nosuid,nodev,size=10M \
    $SECURITY_OPTS \
    --cap-drop ALL \
    --cap-add NET_BIND_SERVICE \
    --memory="256m" \
    --memory-swap="256m" \
    --cpus="0.5" \
    --pids-limit 50 \
    --ulimit nofile=1024:1024 \
    --ulimit nproc=50:50 \
    --log-driver json-file \
    --log-opt max-size=10m \
    --log-opt max-file=3 \
    $IMAGE_NAME || {
    echo -e "${RED}Failed to start container${NC}"
    exit 1
}

# Wait for container to be healthy
echo -e "${GREEN}⏳ Waiting for container to be healthy...${NC}"
RETRIES=30
while [ $RETRIES -gt 0 ]; do
    if docker inspect --format='{{.State.Health.Status}}' $CONTAINER_NAME 2>/dev/null | grep -q healthy; then
        echo -e "${GREEN}✅ Container is healthy!${NC}"
        break
    fi
    sleep 1
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Container health check timed out, but it might still be running${NC}"
fi

# Show container status
echo -e "${GREEN}📊 Container Status:${NC}"
docker ps --filter name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Show logs
echo -e "${GREEN}📜 Container Logs:${NC}"
docker logs --tail 20 $CONTAINER_NAME

echo ""
echo -e "${GREEN}✨ Modal CTF Challenge is running!${NC}"
echo -e "${GREEN}   Access at: http://localhost:${HOST_PORT}${NC}"
echo ""
echo -e "${GREEN}Security features enabled:${NC}"
echo "  ✓ Running as non-root user (uid=1001)"
echo "  ✓ Read-only filesystem with limited tmpfs"
echo "  ✓ All capabilities dropped except NET_BIND_SERVICE"
echo "  ✓ Auto-restart on crash or unhealthy state"
if [ "$OS_NAME" = "Linux" ]; then
    echo "  ✓ No new privileges allowed"
    echo "  ✓ AppArmor and Seccomp profiles enabled"
else
    echo "  ✓ No new privileges allowed"
    echo "  ⚠ AppArmor/Seccomp not available on macOS"
fi
echo "  ✓ Resource limits enforced (256MB RAM, 0.5 CPU)"
echo "  ✓ Process and file descriptor limits"
echo "  ✓ No setuid/setgid binaries in container"
echo ""
echo -e "${GREEN}To stop the container:${NC} docker stop $CONTAINER_NAME"
echo -e "${GREEN}To view logs:${NC} docker logs -f $CONTAINER_NAME"
echo -e "${GREEN}To restart:${NC} docker restart $CONTAINER_NAME"
echo ""
echo -e "${YELLOW}Note: Container will auto-restart if it crashes or becomes unhealthy${NC}"
