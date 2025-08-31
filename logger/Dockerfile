FROM python:3.11-slim

# Create non-root user
RUN groupadd -g 1002 logger && \
    useradd -r -u 1002 -g logger -d /app -s /sbin/nologin logger && \
    mkdir -p /app /logs && \
    chown -R logger:logger /app && \
    chown -R logger:logger /logs

WORKDIR /app

# Install minimal dependencies
RUN pip install --no-cache-dir fastapi uvicorn

# Copy logger service
COPY --chown=logger:logger logger_service.py ./

# Switch to non-root user
USER logger

# Only expose internally (not published to host)
EXPOSE 9090

# Run the logger service
CMD ["python3", "-u", "logger_service.py"]
