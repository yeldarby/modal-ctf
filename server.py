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

# Import rfmodal (our secure fork of modal)
# Note: rfmodal package installs as 'modal' module
try:
    import modal
except ImportError:
    print("Error: rfmodal not found. Please install with: pip install rfmodal")
    print("The Docker image should have rfmodal pre-installed")
    sys.exit(1)

# Check if running in vulnerable mode
VULNERABLE_MODE = os.environ.get("VULNERABLE", "false").lower() in ["true", "1", "yes"]

# Logger configuration
LOGGER_URL = os.environ.get("LOGGER_URL")
LOGGER_SECRET = os.environ.get("LOGGER_SECRET", "default-secret-change-me")

# Set the FLAG environment variable for the CTF
if "FLAG" not in os.environ:
    print("⚠️  WARNING: FLAG environment variable not set!")
    print("   Set it with: export FLAG='CTF{your_flag_here}'")
    os.environ["FLAG"] = "CTF{default_flag_for_testing}"

# Create FastAPI app
app = FastAPI(
    title="Modal CTF Challenge",
    description=f"Running in {'VULNERABLE' if VULNERABLE_MODE else 'SECURE'} mode"
)

async def log_to_sidecar(code: str, output: dict, client_ip: str, user_agent: str):
    """Send log entry to the logger sidecar service"""
    if not LOGGER_URL:
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
        
        # Send to logger service
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{LOGGER_URL}/log",
                json=log_data,
                timeout=2.0  # Short timeout to not block main service
            )
    except Exception as e:
        # Silently fail - logging should not break main service
        print(f"Logger error (non-critical): {e}", file=sys.stderr)

# Serve static files from public directory
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path("public/index.html")
    if html_path.exists():
        content = html_path.read_text()
        
        # Determine the base URL
        base_url = os.environ.get("BASE_URL")
        if not base_url:
            # Auto-detect based on environment
            port = os.environ.get("PORT", "80")
            # In Docker, we're always on the internal port, external mapping handles the rest
            if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER"):
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
        "flag_configured": "FLAG" in os.environ,
        "modal_configured": bool(os.environ.get("MODAL_TOKEN_ID")),
        "container": os.path.exists("/.dockerenv") or bool(os.environ.get("DOCKER_CONTAINER")),
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
    port = int(os.environ.get("PORT", "80"))
    base_url = os.environ.get("BASE_URL")
    
    # Detect if running in Docker
    in_docker = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER")
    
    print("=" * 60)
    print("Modal CTF Challenge - Local Server")
    print("=" * 60)
    print(f"MODE: {'VULNERABLE' if VULNERABLE_MODE else 'SECURE'}")
    print(f"Pickle Firewall: {'DISABLED ⚠️' if VULNERABLE_MODE else 'ENABLED ✅'}")
    print(f"FLAG is set to: {os.environ.get('FLAG', 'NOT SET')}")
    print(f"Running as user: {os.environ.get('USER', 'unknown')}")
    print(f"Hostname: {os.uname().nodename}")
    print(f"Container: {'Yes (Docker)' if in_docker else 'No (Direct)'}")
    print(f"Python version: {sys.version}")
    print(f"Logger: {'Configured' if LOGGER_URL else 'Not configured'}")
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
