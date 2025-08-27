# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    libffi-dev \
    libssl-dev \
    python3-dev \
    pkg-config \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Upgrade pip, setuptools, and wheel
RUN pip install --upgrade pip setuptools wheel

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies (without taskess)
RUN pip install --no-cache-dir -r requirements.txt

# Set Python path to include the app directory
ENV PYTHONPATH=/app

# Copy the taskes package
COPY taskes/ /app/taskes/

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/uploads /app/cache_slices /app/processed /app/data

# Set permissions
RUN chmod -R 755 /app

# Expose port (for web service)
EXPOSE 5001

# Default command (overridden by docker-compose). Run the factory entrypoint.
CMD ["python", "run.py"]