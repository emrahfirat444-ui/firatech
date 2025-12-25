#!/bin/bash
# ACI'ye cron job eklemek için script
# Container içinde çalıştırılacak

# Günlük 03:00 UTC'de scraping job'u çalıştır
(crontab -l 2>/dev/null; echo "0 3 * * * cd /app && python scheduler_job.py >> /var/log/scraper.log 2>&1") | crontab -

# If STOP_COSTS is enabled (default), do not run cron — sleep indefinitely instead
if [ "${STOP_COSTS:-1}" = "1" ]; then
	echo "STOP_COSTS=1 - cron disabled to avoid cost incurrence. Sleeping indefinitely."
	exec sleep infinity
fi

crond -f
