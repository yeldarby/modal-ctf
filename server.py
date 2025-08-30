#!/usr/bin/env python3
"""
Local FastAPI server that runs on the host VM and calls the Modal function.
This server will be vulnerable to the pickle deserialization attack.
"""

import os
import json
import modal
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from pathlib import Path
import uvicorn
import sys

# Set the FLAG environment variable for the CTF
if "FLAG" not in os.environ:
    print("⚠️  WARNING: FLAG environment variable not set!")
    print("   Set it with: export FLAG='CTF{your_flag_here}'")
    os.environ["FLAG"] = "CTF{default_flag_for_testing}"

# Create FastAPI app
app = FastAPI(title="Modal CTF Challenge")

# Serve static files from public directory
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path("public/index.html")
    if html_path.exists():
        content = html_path.read_text()
        # Replace placeholder with actual URL
        port = os.environ.get("PORT", "80")
        # In Docker, we're always on the internal port, external mapping handles the rest
        if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER"):
            # Running in Docker
            base_url = "http://localhost"
        else:
            # Running directly
            base_url = f"http://localhost:{port}" if port != "80" else "http://localhost"
        content = content.replace("[YOUR_URL]", base_url)
        return content
    return "<h1>Error: public/index.html not found</h1>"

@app.post("/execute")
async def execute_code(request: Request):
    """
    Execute user-provided Python code in a Modal restricted function.
    
    Accepts raw Python code as the request body (no JSON wrapper).
    
    VULNERABILITY: The result from Modal is unpickled, allowing arbitrary code
    execution if the returned object has a malicious __reduce__ method.
    """
    try:
        # Get raw body as Python code
        code = await request.body()
        code = code.decode('utf-8')
        
        # Get the Modal function
        modal_function = modal.Function.from_name(
            "modal-ctf-challenge", 
            "run_untrusted_code"
        )
        
        # Call the Modal function remotely
        # The vulnerability happens here when Modal pickles/unpickles the result
        result = modal_function.remote(code)
        
        response_data = {
            "success": True,
            "result": result.get("result"),
            "output": result.get("output"),
            "error": result.get("error")
        }
        
        # Return pretty-printed JSON
        pretty_json = json.dumps(response_data, indent=2)
        return Response(content=pretty_json, media_type="application/json")
        
    except Exception as e:
        response_data = {
            "success": False,
            "error": f"Failed to execute code: {str(e)}",
            "details": str(type(e).__name__)
        }
        pretty_json = json.dumps(response_data, indent=2)
        return Response(content=pretty_json, media_type="application/json", status_code=500)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "flag_configured": "FLAG" in os.environ,
        "modal_configured": bool(os.environ.get("MODAL_TOKEN_ID")),
        "container": os.path.exists("/.dockerenv") or bool(os.environ.get("DOCKER_CONTAINER")),
        "hostname": os.uname().nodename
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "80"))
    
    # Detect if running in Docker
    in_docker = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER")
    
    print("=" * 60)
    print("Modal CTF Challenge - Local Server")
    print("=" * 60)
    print(f"FLAG is set to: {os.environ.get('FLAG', 'NOT SET')}")
    print(f"Running as user: {os.environ.get('USER', 'unknown')}")
    print(f"Hostname: {os.uname().nodename}")
    print(f"Container: {'Yes (Docker)' if in_docker else 'No (Direct)'}")
    print(f"Python version: {sys.version}")
    print()
    print(f"Starting server on http://0.0.0.0:{port}")
    print("=" * 60)
    
    # Note: Port 80 requires sudo on most systems when not in Docker
    if port < 1024 and os.geteuid() != 0 and not in_docker:
        print("\n⚠️  WARNING: Port 80 requires root privileges!")
        print("   Run with: sudo python3 server.py")
        print("   Or set PORT=8000 for non-privileged port")
    
    # Flush output for Docker logs
    sys.stdout.flush()
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
