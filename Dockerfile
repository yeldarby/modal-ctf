# Multi-stage build for minimal attack surface
FROM python:3.11-slim AS builder

# Install dependencies in builder stage
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final minimal image
FROM python:3.11-slim

# Create non-root user with specific UID/GID
RUN groupadd -g 1001 ctfuser && \
    useradd -r -u 1001 -g ctfuser -d /app -s /sbin/nologin ctfuser && \
    mkdir -p /app && \
    chown -R ctfuser:ctfuser /app

# Copy only necessary Python packages from builder
COPY --from=builder --chown=ctfuser:ctfuser /root/.local /home/ctfuser/.local

# Set working directory
WORKDIR /app

# Copy application files with proper ownership
COPY --chown=ctfuser:ctfuser server.py modal_function.py ./
COPY --chown=ctfuser:ctfuser public ./public

# Remove any setuid/setgid binaries to prevent privilege escalation
RUN find / -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

# Ensure Python packages are in PATH for non-root user
ENV PATH="/home/ctfuser/.local/bin:${PATH}"
ENV PYTHONPATH="/home/ctfuser/.local/lib/python3.11/site-packages:${PYTHONPATH:-}"

# Set USER environment variable to match the actual user
ENV USER=ctfuser

# Mark as Docker container
ENV DOCKER_CONTAINER=1

# Switch to non-root user
USER ctfuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# Run on non-privileged port (will be mapped to 80 by Docker)
ENV PORT=8080

# Use exec form to ensure proper signal handling
ENTRYPOINT ["python3", "-u", "server.py"]
