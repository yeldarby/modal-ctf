#!/usr/bin/env python3
"""
Secure logger service that only accepts write operations.
No read or modify capabilities to prevent exploitation if main container is compromised.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
import uvicorn
import hashlib
import hmac

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

# Generate a random secret key for HMAC authentication
# In production, this should be set via environment variable shared only with main container
LOGGER_SECRET = get_env("LOGGER_SECRET", "default-secret-change-me")

app = FastAPI(
    title="CTF Logger Service",
    description="Write-only logging service for CTF challenge",
    docs_url=None,  # Disable Swagger UI
    redoc_url=None  # Disable ReDoc
)

class LogEntry(BaseModel):
    """Log entry model with validation"""
    code: str = Field(..., description="User-submitted code")
    output: dict = Field(..., description="Response sent to user")
    client_ip: str = Field(..., description="Client IP address")
    user_agent: str = Field(default="", description="User agent string")
    hmac_signature: str = Field(..., description="HMAC signature for authentication")

def verify_hmac(data: dict, signature: str) -> bool:
    """Verify HMAC signature to ensure request is from authorized source"""
    # Create a copy without the signature field
    data_copy = {k: v for k, v in data.items() if k != "hmac_signature"}
    message = json.dumps(data_copy, sort_keys=True)
    expected_signature = hmac.new(
        LOGGER_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Debug logging
    if signature != expected_signature:
        print(f"HMAC mismatch:", file=sys.stderr)
        print(f"  Received: {signature[:16]}...", file=sys.stderr)
        print(f"  Expected: {expected_signature[:16]}...", file=sys.stderr)
        print(f"  Secret used: {LOGGER_SECRET[:8]}...", file=sys.stderr)
    
    return hmac.compare_digest(signature, expected_signature)

@app.post("/log")
async def log_entry(entry: LogEntry):
    """
    Write-only endpoint to log CTF attempts.
    No read capability to prevent information disclosure if compromised.
    """
    # Verify HMAC signature (use model_dump instead of deprecated dict)
    if not verify_hmac(entry.model_dump(), entry.hmac_signature):
        print(f"HMAC verification failed for request from {entry.client_ip}", file=sys.stderr)
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Generate timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    
    # Prepare metadata
    metadata = {
        "timestamp": datetime.utcnow().isoformat(),
        "client_ip": entry.client_ip,
        "user_agent": entry.user_agent,
        "output_success": entry.output.get("success", False),
        "mode": entry.output.get("mode", "unknown")
    }
    
    try:
        # Create log directory if it doesn't exist
        log_dir = Path("/logs")
        log_dir.mkdir(exist_ok=True, mode=0o750)  # rwxr-x--- for directory traversal only
        
        # Write metadata file - NO EXECUTE PERMISSIONS
        metadata_file = log_dir / f"{timestamp}-metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        metadata_file.chmod(0o640)  # rw-r----- : NO EXECUTE
        
        # Write input code - NO EXECUTE PERMISSIONS
        input_file = log_dir / f"{timestamp}-input.txt"
        input_file.write_text(entry.code)
        input_file.chmod(0o640)  # rw-r----- : NO EXECUTE
        
        # Write output - NO EXECUTE PERMISSIONS
        output_file = log_dir / f"{timestamp}-output.json"
        output_file.write_text(json.dumps(entry.output, indent=2))
        output_file.chmod(0o640)  # rw-r----- : NO EXECUTE
        
        print(f"Successfully logged entry at {timestamp} from {entry.client_ip}", file=sys.stderr)
        return {"status": "logged", "timestamp": timestamp}
        
    except Exception as e:
        # Log the actual error for debugging
        print(f"Logging error: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Logging failed")

@app.get("/health")
async def health():
    """Basic health check endpoint"""
    return {"status": "healthy"}

# No other endpoints - strictly write-only service

if __name__ == "__main__":
    print("=" * 60)
    print("CTF Logger Service")
    print("=" * 60)
    print("Write-only logging service")
    print("No read or list capabilities")
    print(f"Running on http://0.0.0.0:9090")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=9090, log_level="warning")
