FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libavahi-client3 \
    libavahi-common3 \
    avahi-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY sonorium/ ./sonorium/
COPY wrapper/ ./wrapper/
COPY main.py .

# Expose port
EXPOSE 8099

# Run the application
CMD ["python", "main.py"]
