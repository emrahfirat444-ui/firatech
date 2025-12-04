#!/bin/sh
set -e

# Default PORT environment variable (should be provided by container runtime)
PORT=${PORT:-80}

echo "Starting Streamlit on port ${PORT}..."
exec streamlit run app.py --server.port ${PORT} --server.address 0.0.0.0
