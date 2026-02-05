# the folders /app/configs and /app/data and /app/database are mapped folders
# see the note named 'Short version : create a docker container from flask app' to see how to install the docker container on the SYNDEV Nas

# Use Python base image - Debian-based for easier management
FROM python:3.12-slim

# Install cron and essential tools for interactive terminal access
RUN apt-get update && apt-get install -y \
    cron \
    bash \
    curl \
    wget \
    vim \
    nano \
    htop \
    procps \
    tree \
    less \
    grep \
    findutils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy your application files
COPY *.py *.sh *.yaml *.txt /app/



# Install Python dependencies (if you have requirements.txt)
# Uncomment the next two lines if you have a requirements.txt file
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Set environment variables for better terminal experience
ENV TERM=xterm-256color
ENV PYTHONUNBUFFERED=1

# Set up cron jobs directly in the image
# (minutes hours day_of_month month day_of_week )

RUN echo "0 6 * * * /usr/local/bin/python /app/energy_data_collector.py >> /var/log/energy_data_collector.log 2>&1" > /etc/cron.d/all_crons && \
    chmod 0644 /etc/cron.d/all_crons && \
    crontab /etc/cron.d/all_crons


# Create startup script to run both cron and keep container alive
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'service cron start' >> /app/start.sh && \
    echo 'uvicorn webapp:app --host 0.0.0.0 --port 8000 &' >> /app/start.sh && \
    echo 'tail -f /dev/null' >> /app/start.sh && \
    chmod +x /app/start.sh
# Expose port 8000 for the uvicorn app ( webapp.py)
EXPOSE 8000

# define the volume to be saved on the server
VOLUME /app/data /volume1/docker/energiepark

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run as root to avoid permission issues (simpler for development)
# Default command - start cron and keep container running for terminal access


# Set entrypoint
CMD ["/app/start.sh"]