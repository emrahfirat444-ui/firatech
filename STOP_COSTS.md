STOP_COSTS
=========

This repository includes a safety mechanism to prevent accidental cost-incurring operations (cloud deploys, scheduled scrapers, container entrypoints, cron jobs).

Behavior
- If `STOP_COSTS` environment variable is set to `1` (default), the following are disabled:
  - Background scheduler (`scheduler_background.py`, `scheduler_job.py`)
  - Docker entrypoints (`docker-entrypoint.sh`, `docker-cron-entrypoint.sh`) — they will sleep indefinitely instead of starting jobs
  - Azure Timer trigger functions (`azure_function_timer.py`, `TimerTrigger/azure_function_timer.py`) — they will no-op
  - `deploy-to-azure.ps1` — aborts unless `ALLOW_DEPLOY=1` is set

How to re-enable
- To re-enable runtime behavior, set environment variables appropriately in your execution environment (not recommended on shared or production accounts without review):

  - `STOP_COSTS=0`  # allow schedulers/entrypoints to run
  - `ALLOW_DEPLOY=1`  # required to allow `deploy-to-azure.ps1` to proceed

Notes
- Defaults are intentionally conservative to avoid accidental cloud costs.
- If you want a different default, edit the files that check `STOP_COSTS` explicitly.
