# CTF Logger Sidecar Service

## Overview

This is a secure, write-only logging service that runs as a sidecar container alongside the main CTF challenge. It logs all user attempts to a persistent volume without exposing any read or modify capabilities.

## Security Features

1. **Write-Only API**: The service only exposes a single `/log` endpoint for writing. There are no endpoints to read, list, or modify existing logs.

2. **HMAC Authentication**: All log requests must include a valid HMAC-SHA256 signature using a shared secret between the main container and logger.

3. **Network Isolation**: The logger service is only accessible within the Docker network, not exposed to the host or internet.

4. **Minimal Attack Surface**:
   - Runs as non-root user (UID 1002)
   - Read-only root filesystem
   - No unnecessary capabilities
   - Memory and CPU limits
   - Minimal dependencies

5. **Persistent Storage**: Logs are written to `/home/yeldarb/output` on the host with restrictive permissions (700).

## Log Format

Each CTF attempt creates three files:

- `{timestamp}-metadata.json`: Request metadata (IP, user agent, timestamp)
- `{timestamp}-input.txt`: The code submitted by the user
- `{timestamp}-output.json`: The response sent back to the user

## Architecture

```
Internet → modal-ctf container → logger container → /home/yeldarb/output/
              ↓                      ↑
         Modal Function         (Internal network only)
```

## Deployment

The logger is automatically deployed as part of the docker-compose stack:

```bash
docker-compose up -d
```

## Monitoring

View logger health:
```bash
docker logs modal-ctf-logger
```

Check logged attempts:
```bash
ls -la /home/yeldarb/output/
```

## Security Considerations

- The logger secret (`LOGGER_SECRET`) should be kept secure and only shared between the main container and logger
- The `/home/yeldarb/output` directory has restrictive permissions (700) with ownership by the logger user
- Even if the main container is compromised via RCE, the attacker cannot read or modify existing logs
- The logger service itself has no ability to execute user code or access the FLAG
