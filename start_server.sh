#!/bin/bash
# Start the CTF server on the host VM

set -e

echo "Modal CTF - Starting Server"
echo "==========================="
echo

# Check if FLAG is set
if [ -z "$FLAG" ]; then
    echo "⚠️  WARNING: FLAG environment variable not set!"
    echo "The CTF will use a default flag for testing."
    echo "Set a real flag with: export FLAG='CTF{your_flag_here}'"
    echo
    read -p "Continue with default flag? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check dependencies
if ! python3 -c "import modal, fastapi, uvicorn" 2>/dev/null; then
    echo "ERROR: Missing Python dependencies!"
    echo "Install with: pip3 install -r requirements.txt"
    exit 1
fi

# Check if Modal function is deployed
echo "Checking Modal function deployment..."
if ! python3 -c "import modal; f = modal.Function.from_name('modal-ctf-challenge', 'run_untrusted_code')" 2>/dev/null; then
    echo "ERROR: Modal function not deployed!"
    echo "Deploy with: ./deploy_modal.sh"
    exit 1
fi

echo "✅ Modal function is deployed"
echo

# Determine port
PORT=${PORT:-80}
HOST_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")

echo "Configuration:"
echo "  FLAG: ${FLAG:-[NOT SET - using default]}"
echo "  PORT: $PORT"
echo "  HOST: $HOST_IP"
echo

# Start server
if [ "$PORT" -lt 1024 ]; then
    echo "Port $PORT requires root privileges..."
    echo
    echo "Starting server at http://$HOST_IP/"
    echo "========================================="
    sudo FLAG="$FLAG" PORT="$PORT" python3 server.py
else
    echo "Starting server at http://$HOST_IP:$PORT/"
    echo "========================================="
    PORT="$PORT" python3 server.py
fi
