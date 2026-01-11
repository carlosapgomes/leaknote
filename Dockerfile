FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash leaknote

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=leaknote:leaknote bot/ ./bot/
COPY --chown=leaknote:leaknote leaknote/ ./leaknote/
COPY --chown=leaknote:leaknote scripts/ ./scripts/
COPY --chown=leaknote:leaknote prompts/ ./prompts/
COPY --chown=leaknote:leaknote schema.sql .

# Copy entrypoint
COPY --chown=leaknote:leaknote entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create logs directory
RUN mkdir -p /app/logs && chown leaknote:leaknote /app/logs

# Switch to non-root user
USER leaknote

# Entrypoint handles waiting for database
ENTRYPOINT ["/entrypoint.sh"]

# Default command: run the bot
CMD ["python", "bot/main.py"]
