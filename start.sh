#!/bin/bash

# Startup script for Hugging Face Spaces
echo "🚀 Starting Data Analysis Agent..."

# Set default environment variables if not provided
export PYTHONPATH="${PYTHONPATH}:/app"
export MPLBACKEND="Agg"

# Handle Hugging Face Spaces environment
if [ -n "$SPACE_ID" ]; then
    echo "🔧 Running in Hugging Face Spaces environment: $SPACE_ID"
    # Set any specific configurations for HF Spaces
    export HF_SPACES=true
fi

# Create temp directories
mkdir -p /tmp/uploads
mkdir -p /tmp/plots

# Ensure permissions
chmod 755 /tmp/uploads
chmod 755 /tmp/plots

echo "✅ Environment setup complete"

# Start the application
exec uvicorn backend.main:app --host 0.0.0.0 --port 7860 --workers 1
