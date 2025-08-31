#!/usr/bin/env python3
"""
Local FastAPI server that runs on the host VM and calls the Modal function.
Can run in two modes:
- Secure mode (default): Uses rfmodal's pickle firewall to prevent RCE
- Vulnerable mode: Disables firewall to allow pickle deserialization attacks
"""

import os
import json
import sys
import hashlib
import hmac
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from pathlib import Path
import uvicorn

def strip_quotes(value: str) -> str:
    """Strip surrounding quotes from environment variable values if present."""
    if value and len(value) >= 2:
        if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
            return value[1:-1]
    return value

def get_env(key: str, default: str = None) -> str:
    """Get environment variable and strip any surrounding quotes."""
    value = os.environ.get(key, default)
    if value is not None:
        return strip_quotes(value)
    return value

# Clean up Modal tokens if they have quotes
if "MODAL_TOKEN_ID" in os.environ:
    os.environ["MODAL_TOKEN_ID"] = strip_quotes(os.environ["MODAL_TOKEN_ID"])
if "MODAL_TOKEN_SECRET" in os.environ:
    os.environ["MODAL_TOKEN_SECRET"] = strip_quotes(os.environ["MODAL_TOKEN_SECRET"])

# Import rfmodal (our secure fork of modal)
# Note: rfmodal package installs as 'modal' module
try:
    import modal
except ImportError:
    print("Error: rfmodal not found. Please install with: pip install rfmodal")
    print("The Docker image should have rfmodal pre-installed")
    sys.exit(1)

# Check if running in vulnerable mode
VULNERABLE_MODE = get_env("VULNERABLE", "false").lower() in ["true", "1", "yes"]

# Logger configuration
LOGGER_URL = get_env("LOGGER_URL")
LOGGER_SECRET = get_env("LOGGER_SECRET", "default-secret-change-me")

# Set the FLAG environment variable for the CTF
FLAG = get_env("FLAG")
if not FLAG:
    print("⚠️  WARNING: FLAG environment variable not set!")
    print("   Set it with: export FLAG='CTF{your_flag_here}'")
    FLAG = "CTF{default_flag_for_testing}"
    os.environ["FLAG"] = FLAG
else:
    # Update the environment variable with the cleaned value
    os.environ["FLAG"] = FLAG

# Create FastAPI app
app = FastAPI(
    title="Modal CTF Challenge",
    description=f"Running in {'VULNERABLE' if VULNERABLE_MODE else 'SECURE'} mode"
)

async def log_to_sidecar(code: str, output: dict, client_ip: str, user_agent: str):
    """Send log entry to the logger sidecar service"""
    if not LOGGER_URL:
        print(f"Logger not configured - LOGGER_URL is empty", file=sys.stderr)
        return  # Logger not configured
    
    try:
        # Prepare data for HMAC
        log_data = {
            "code": code,
            "output": output,
            "client_ip": client_ip,
            "user_agent": user_agent
        }
        
        # Calculate HMAC signature
        message = json.dumps(log_data, sort_keys=True)
        signature = hmac.new(
            LOGGER_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Add signature to data
        log_data["hmac_signature"] = signature
        
        print(f"Sending log to {LOGGER_URL}/log with signature {signature[:8]}...", file=sys.stderr)
        
        # Send to logger service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LOGGER_URL}/log",
                json=log_data,
                timeout=5.0  # Increased timeout
            )
            if response.status_code != 200:
                print(f"Logger returned status {response.status_code}: {response.text}", file=sys.stderr)
            else:
                print(f"Successfully logged to sidecar", file=sys.stderr)
    except Exception as e:
        # Log the actual error for debugging
        print(f"Logger error (non-critical): {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

# Serve static files from public directory
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path("public/index.html")
    if html_path.exists():
        content = html_path.read_text()
        
        # Determine the base URL
        base_url = get_env("BASE_URL")
        if not base_url:
            # Auto-detect based on environment
            port = get_env("PORT", "80")
            # In Docker, we're always on the internal port, external mapping handles the rest
            if os.path.exists("/.dockerenv") or get_env("DOCKER_CONTAINER"):
                # Running in Docker
                base_url = "http://localhost"
            else:
                # Running directly
                base_url = f"http://localhost:{port}" if port != "80" else "http://localhost"
        
        # Replace placeholder with actual URL
        content = content.replace("[YOUR_URL]", base_url)
        
        # Update the description based on mode
        if not VULNERABLE_MODE:
            secure_note = """
        <div style='background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; padding: 10px; margin: 20px 0; color: #155724;'>
            <strong>🛡️ SECURE MODE:</strong> rfmodal's pickle firewall is active. Standard pickle attacks will be blocked.
        </div>
        """
            content = content.replace('<h1>🚩 Modal CTF Challenge - Capture the Flag! 🚩</h1>', 
                                    f'<h1>🚩 Modal CTF Challenge - Capture the Flag! 🚩</h1>\n    {secure_note}')
        
        return content
    return "<h1>Error: public/index.html not found</h1>"

@app.post("/execute")
async def execute_code(request: Request):
    """
    Execute user-provided Python code in a Modal restricted function.
    
    Accepts raw Python code as the request body (no JSON wrapper).
    
    Security modes:
    - SECURE (default): Uses rfmodal's pickle firewall to block malicious deserialization
    - VULNERABLE: Disables firewall, allowing pickle RCE attacks for CTF purposes
    """
    # Get client info for logging
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    try:
        # Handle both raw text and JSON input
        content_type = request.headers.get("content-type", "").lower()
        
        if "application/json" in content_type:
            body = await request.json()
            code = body.get("code", "")
        else:
            # Treat as raw text/plain
            body_bytes = await request.body()
            code = body_bytes.decode("utf-8")
        
        # Get the Modal function with appropriate firewall setting
        modal_function = modal.Function.from_name(
            "modal-ctf-challenge", 
            "run_untrusted_code",
            use_firewall=not VULNERABLE_MODE  # Enable firewall unless in vulnerable mode
        )
        
        # Call the Modal function remotely
        # In secure mode, rfmodal's firewall will block malicious pickle operations
        # In vulnerable mode, the attack will work as before
        result = modal_function.remote(code)
        
        response_data = {
            "success": True,
            "result": result.get("result"),
            "output": result.get("output"),
            "error": result.get("error"),
            "mode": "vulnerable" if VULNERABLE_MODE else "secure"
        }
        
        # Log the attempt
        await log_to_sidecar(code, response_data, client_ip, user_agent)
        
        # Return pretty-printed JSON
        pretty_json = json.dumps(response_data, indent=2)
        return Response(content=pretty_json, media_type="application/json")
        
    except Exception as e:
        # Check if this is a firewall-blocked pickle operation
        error_message = str(e)
        is_firewall_block = "rffickle" in error_message.lower() or "firewall" in error_message.lower()
        
        response_data = {
            "success": False,
            "error": f"Failed to execute code: {error_message}",
            "details": str(type(e).__name__),
            "mode": "vulnerable" if VULNERABLE_MODE else "secure",
            "firewall_blocked": is_firewall_block and not VULNERABLE_MODE
        }
        
        if is_firewall_block and not VULNERABLE_MODE:
            response_data["hint"] = "The pickle firewall blocked your attack. This is expected in secure mode!"
        
        # Log the attempt
        await log_to_sidecar(code, response_data, client_ip, user_agent)
        
        pretty_json = json.dumps(response_data, indent=2)
        return Response(content=pretty_json, media_type="application/json", status_code=500)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mode": "vulnerable" if VULNERABLE_MODE else "secure",
        "firewall_enabled": not VULNERABLE_MODE,
        "flag_configured": bool(FLAG),
        "modal_configured": bool(get_env("MODAL_TOKEN_ID")),
        "container": os.path.exists("/.dockerenv") or bool(get_env("DOCKER_CONTAINER")),
        "hostname": os.uname().nodename,
        "rfmodal_version": getattr(modal, "__version__", "unknown"),
        "logger_configured": bool(LOGGER_URL)
    }

@app.get("/mode")
async def mode():
    """Get current security mode."""
    return {
        "mode": "vulnerable" if VULNERABLE_MODE else "secure",
        "firewall_enabled": not VULNERABLE_MODE,
        "description": "Pickle attacks WILL work" if VULNERABLE_MODE else "Pickle attacks are BLOCKED"
    }

if __name__ == "__main__":
    port = int(get_env("PORT", "80"))
    base_url = get_env("BASE_URL")
    
    # Detect if running in Docker
    in_docker = os.path.exists("/.dockerenv") or get_env("DOCKER_CONTAINER")
    
    print("=" * 60)
    print("Modal CTF Challenge - Local Server")
    print("=" * 60)
    print(f"MODE: {'VULNERABLE' if VULNERABLE_MODE else 'SECURE'}")
    print(f"Pickle Firewall: {'DISABLED ⚠️' if VULNERABLE_MODE else 'ENABLED ✅'}")
    print(f"FLAG is set to: {FLAG}")
    print(f"Running as user: {get_env('USER', 'unknown')}")
    print(f"Hostname: {os.uname().nodename}")
    print(f"Container: {'Yes (Docker)' if in_docker else 'No (Direct)'}")
    print(f"Python version: {sys.version}")
    print(f"Logger: {'Configured' if LOGGER_URL else 'Not configured'}")
    print(f"Logger URL: {LOGGER_URL if LOGGER_URL else 'Not set'}")
    print(f"Logger Secret: {LOGGER_SECRET[:8]}..." if LOGGER_SECRET else "Not set")
    if base_url:
        print(f"Base URL: {base_url}")
    print()
    
    if VULNERABLE_MODE:
        print("⚠️  WARNING: Running in VULNERABLE mode!")
        print("   Pickle deserialization attacks WILL work!")
    else:
        print("🛡️  Running in SECURE mode")
        print("   rfmodal's pickle firewall is active")
        print("   Standard pickle attacks will be blocked")
    
    print()
    print(f"Starting server on http://0.0.0.0:{port}")
    if base_url:
        print(f"Public access: {base_url}")
    print("=" * 60)
    
    # Note: Port 80 requires sudo on most systems when not in Docker
    if port < 1024 and os.geteuid() != 0 and not in_docker:
        print("\n⚠️  WARNING: Port 80 requires root privileges!")
        print("   Run with: sudo python3 server.py")
        print("   Or set PORT=8000 for non-privileged port")
    
    # Flush output for Docker logs
    sys.stdout.flush()
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
