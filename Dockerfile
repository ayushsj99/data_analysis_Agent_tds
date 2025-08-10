# Use Python 3.11 slim image for efficiency
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for the packages
RUN apt-get update && apt-get install -y \
    # For building Python packages
    build-essential \
    # For PDF processing (pdfplumber, PyPDF2)
    poppler-utils \
    # For image processing (PIL/Pillow)
    libjpeg-dev \
    libpng-dev \
    # For lxml and beautifulsoup4
    libxml2-dev \
    libxslt1-dev \
    # For scientific computing
    libatlas-base-dev \
    liblapack-dev \
    libblas-dev \
    gfortran \
    # For matplotlib backend
    libfreetype6-dev \
    pkg-config \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Create necessary directories
RUN mkdir -p /tmp/uploads /tmp/plots

# Set matplotlib backend to Agg for server environment
ENV MPLBACKEND=Agg

# Expose the port
EXPOSE 7860

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Add curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app && \
    chmod -R 755 /app

USER app

# Command to run the application
CMD ["./start.sh"]