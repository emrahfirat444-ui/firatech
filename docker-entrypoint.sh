#!/bin/sh
set -e

# Default PORT environment variable (should be provided by container runtime)
PORT=${PORT:-80}

echo "Starting background scheduler job..."
# If STOP_COSTS is enabled, avoid starting background processes (default: enabled)
if [ "${STOP_COSTS:-1}" = "1" ]; then
	echo "STOP_COSTS=1 - not starting background jobs or Streamlit to avoid costs. Sleeping indefinitely."
	exec sleep infinity
fi
# Background'da günde 1 kez scraping çalıştır (APScheduler kullanarak)
python /app/scheduler_background.py > /var/log/scheduler.log 2>&1 &

echo "Starting Streamlit on port ${PORT}..."
streamlit run app.py --server.port ${PORT} --server.address 0.0.0.0
