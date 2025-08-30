#!/usr/bin/env python3
"""
Local FastAPI server that runs on the host VM and calls the Modal function.
This server will be vulnerable to the pickle deserialization attack.
"""

import os
import modal
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import uvicorn

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
        
        return JSONResponse({
            "success": True,
            "result": result.get("result"),
            "output": result.get("output"),
            "error": result.get("error"),
            "host_info": {
                "hostname": os.uname().nodename,
                "user": os.environ.get("USER", "unknown"),
                "flag_set": "FLAG" in os.environ
            }
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": f"Failed to execute code: {str(e)}"
        })

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "flag_configured": "FLAG" in os.environ,
        "modal_configured": True
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "80"))
    
    print("=" * 60)
    print("Modal CTF Challenge - Local Server")
    print("=" * 60)
    print(f"FLAG is set to: {os.environ.get('FLAG', 'NOT SET')}")
    print(f"Running as user: {os.environ.get('USER', 'unknown')}")
    print(f"Hostname: {os.uname().nodename}")
    print()
    print(f"Starting server on http://0.0.0.0:{port}")
    print("=" * 60)
    
    # Note: Port 80 requires sudo on most systems
    if port < 1024 and os.geteuid() != 0:
        print("\n⚠️  WARNING: Port 80 requires root privileges!")
        print("   Run with: sudo python3 server.py")
        print("   Or set PORT=8000 for non-privileged port")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
