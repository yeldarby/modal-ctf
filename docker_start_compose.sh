#!/bin/bash

# Docker-compose startup script for Modal CTF with auto-generated logger secret
# This script starts both the main app and logger service

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
HOST_PORT=${HOST_PORT:-80}

# Auto-generate a secure logger secret if not provided
if [ -z "$LOGGER_SECRET" ]; then
    # Generate a random 32-character secret
    LOGGER_SECRET=$(openssl rand -hex 16 2>/dev/null || cat /dev/urandom | head -c 32 | base64 | tr -d '/+=')
    echo -e "${GREEN}🔐 Generated logger secret: ${LOGGER_SECRET:0:8}...${NC}"
fi
export LOGGER_SECRET

# Parse command line arguments
MODE="secure"  # Default to secure mode
if [ "$1" = "vulnerable" ] || [ "$1" = "vuln" ]; then
    MODE="vulnerable"
    echo -e "${YELLOW}⚠️  Starting in VULNERABLE mode - pickle attacks will work!${NC}"
elif [ "$1" = "secure" ] || [ -z "$1" ]; then
    MODE="secure"
    echo -e "${GREEN}🛡️  Starting in SECURE mode - pickle firewall enabled${NC}"
else
    echo -e "${RED}Error: Invalid mode '$1'${NC}"
    echo "Usage: $0 [secure|vulnerable]"
    echo "  secure (default): Enable rfmodal pickle firewall"
    echo "  vulnerable: Disable firewall for CTF exploitation"
    exit 1
fi

# Check if FLAG is set
if [ -z "$FLAG" ]; then
    echo -e "${YELLOW}⚠️  WARNING: FLAG environment variable not set!${NC}"
    echo -e "${YELLOW}   Using default flag for testing.${NC}"
    echo -e "${YELLOW}   Set it with: export FLAG='CTF{your_flag_here}'${NC}"
    FLAG="CTF{default_flag_for_testing}"
fi
export FLAG

# Check if BASE_URL is set (for custom domains)
if [ -n "$BASE_URL" ]; then
    echo -e "${GREEN}Using custom BASE_URL: $BASE_URL${NC}"
    export BASE_URL
else
    echo -e "${BLUE}No BASE_URL set, will use http://localhost${NC}"
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
export MODAL_TOKEN_ID
export MODAL_TOKEN_SECRET

# Check if running as root (needed for port 80)
if [ "$HOST_PORT" -lt 1024 ] && [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Port $HOST_PORT requires root privileges.${NC}"
    echo "Run with: sudo FLAG='$FLAG' ./docker_start_compose.sh $MODE"
    echo "Or set HOST_PORT=8080 for non-privileged port"
    exit 1
fi

# Set VULNERABLE environment variable based on mode
if [ "$MODE" = "vulnerable" ]; then
    export VULNERABLE="true"
    MODE_COLOR=$YELLOW
    MODE_EMOJI="⚠️"
    MODE_DESC="VULNERABLE - Pickle attacks enabled"
else
    export VULNERABLE="false"
    MODE_COLOR=$GREEN
    MODE_EMOJI="🛡️"
    MODE_DESC="SECURE - Pickle firewall active"
fi

# Export HOST_PORT for docker-compose
export HOST_PORT

echo -e "${GREEN}🔨 Starting services with docker-compose...${NC}"
echo -e "${BLUE}   FLAG: ${FLAG}${NC}"
echo -e "${BLUE}   Mode: ${MODE}${NC}"
echo -e "${BLUE}   Logger Secret: ${LOGGER_SECRET:0:8}...${NC}"
echo -e "${BLUE}   Modal Token ID: ${MODAL_TOKEN_ID:0:10}...${NC}"
echo -e "${BLUE}   Host Port: ${HOST_PORT}${NC}"

# Create output directory with proper permissions if it doesn't exist
OUTPUT_DIR="/home/yeldarb/output"
if [ ! -d "$OUTPUT_DIR" ]; then
    echo -e "${GREEN}📁 Creating output directory: $OUTPUT_DIR${NC}"
    sudo mkdir -p "$OUTPUT_DIR"
    # Set ownership to yeldarb user but allow logger container (uid 1002) to write
    sudo chown yeldarb:yeldarb "$OUTPUT_DIR"
    sudo chmod 777 "$OUTPUT_DIR"  # Allow everyone to write (for the logger container)
else
    echo -e "${BLUE}📁 Output directory exists: $OUTPUT_DIR${NC}"
    # Fix permissions if needed - allow logger container to write
    sudo chmod 777 "$OUTPUT_DIR"
    # Also fix any existing files to be readable by yeldarb
    sudo find "$OUTPUT_DIR" -type f -exec chmod 644 {} \; 2>/dev/null || true
fi

# Determine which docker compose command to use
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}Error: Docker Compose is not installed!${NC}"
    echo "Install with one of:"
    echo "  - sudo apt-get install docker-compose"
    echo "  - Or use Docker's built-in compose (should be included with Docker)"
    exit 1
fi
echo -e "${GREEN}✓ Using compose command: $COMPOSE_CMD${NC}"

# Stop any existing containers (both docker-compose and standalone)
echo -e "${GREEN}🧹 Cleaning up existing containers...${NC}"
# Stop and remove any standalone container from old script
docker stop modal-ctf 2>/dev/null || true
docker rm modal-ctf 2>/dev/null || true
# Stop docker-compose services
$COMPOSE_CMD down 2>/dev/null || true

# Build and start services
echo -e "${GREEN}🚀 Building and starting services...${NC}"
$COMPOSE_CMD up -d --build || {
    echo -e "${RED}Failed to start services with docker-compose${NC}"
    echo -e "${RED}Error details:${NC}"
    $COMPOSE_CMD logs --tail=20
    exit 1
}

# Wait for services to be healthy
echo -e "${GREEN}⏳ Waiting for services to be healthy...${NC}"
sleep 3

# Show container status
echo -e "${GREEN}📊 Container Status:${NC}"
$COMPOSE_CMD ps

# Show main service logs
echo -e "${GREEN}📜 Service Logs:${NC}"
$COMPOSE_CMD logs --tail=10

echo ""
echo -e "${MODE_COLOR}✨ Modal CTF Challenge is running in ${MODE} mode!${NC}"
if [ -n "$BASE_URL" ]; then
    echo -e "${GREEN}   Access at: ${BASE_URL}${NC}"
else
    echo -e "${GREEN}   Access at: http://localhost:${HOST_PORT}${NC}"
fi
echo ""

if [ "$MODE" = "vulnerable" ]; then
    echo -e "${YELLOW}${MODE_EMOJI} VULNERABLE MODE ACTIVE ${MODE_EMOJI}${NC}"
    echo -e "${YELLOW}   Pickle deserialization attacks WILL work${NC}"
    echo -e "${YELLOW}   This is for CTF demonstration purposes${NC}"
else
    echo -e "${GREEN}${MODE_EMOJI} SECURE MODE ACTIVE ${MODE_EMOJI}${NC}"
    echo -e "${GREEN}   rfmodal's pickle firewall is enabled${NC}"
    echo -e "${GREEN}   Standard pickle attacks are BLOCKED${NC}"
    echo -e "${BLUE}   Challenge: Find another exploit (if one exists!)${NC}"
fi

echo ""
echo -e "${GREEN}Security features enabled:${NC}"
echo "  ✓ Running as non-root user (uid=1001)"
echo "  ✓ Read-only filesystem with limited tmpfs"
echo "  ✓ All capabilities dropped except NET_BIND_SERVICE"
echo "  ✓ Auto-restart on crash or unhealthy state"
echo "  ✓ Logger service running in separate container"
echo "  ✓ Resource limits enforced (256MB RAM, 0.5 CPU)"
echo "  ✓ Process and file descriptor limits"
echo "  ✓ No setuid/setgid binaries in container"
echo ""
echo -e "${GREEN}Commands:${NC}"
echo -e "  To stop:     $COMPOSE_CMD down"
echo -e "  To logs:     $COMPOSE_CMD logs -f"
echo -e "  To app logs: $COMPOSE_CMD logs -f modal-ctf"
echo -e "  To logger:   $COMPOSE_CMD logs -f logger"
echo -e "  To restart:  $COMPOSE_CMD restart"
echo "  To switch:   ./docker_start_compose.sh [secure|vulnerable]"
echo ""
echo -e "${BLUE}📝 Logs are being written to: $OUTPUT_DIR${NC}"
echo -e "${GREEN}   View logs: ls -la $OUTPUT_DIR${NC}"
echo ""
echo -e "${YELLOW}Note: Containers will auto-restart if they crash or become unhealthy${NC}"

# Instructions for fixing permissions if needed
echo ""
echo -e "${GREEN}📋 Permissions info:${NC}"
echo -e "   Logs directory permissions: $(ls -ld $OUTPUT_DIR | awk '{print $1}')"
echo -e "   You can read all logs in: $OUTPUT_DIR"
echo -e "   Logger container can write new logs"
echo ""
