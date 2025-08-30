#!/bin/bash
# Deploy the Modal function to the cloud

set -e

echo "Modal CTF - Deploying Modal Function"
echo "====================================="
echo

# Check if modal is installed
if ! python3 -c "import modal" 2>/dev/null; then
    echo "ERROR: modal package not installed!"
    echo "Install with: pip3 install modal"
    exit 1
fi

# Check if authenticated with Modal by trying to list apps
# This will fail if not authenticated
if ! python3 -m modal app list &>/dev/null; then
    echo "ERROR: Not authenticated with Modal!"
    echo "Run: python3 -m modal setup"
    exit 1
fi

echo "✓ Modal authentication verified"
echo

# Deploy Modal function
echo "Deploying Modal function to the cloud..."
python3 -m modal deploy modal_function.py

echo
echo "✅ Modal function deployed successfully!"
echo
echo "Next steps:"
echo "1. Set your FLAG: export FLAG='CTF{your_flag_here}'"
echo "2. Start the server: ./start_server.sh (for local testing)"
echo "   OR"
echo "3. Use Docker: ./docker_start.sh (for production deployment)"
