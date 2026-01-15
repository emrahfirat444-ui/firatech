#!/usr/bin/env python3
"""
Backup and remove Proje Analiz and Google Trends artifacts and Trendyol DB.
Creates backups/backup-<timestamp>.zip then deletes target files/dirs.
"""
import os, sys, shutil, zipfile, glob, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(ROOT)

TARGETS = []
# root-level files
for fn in ['proje_analiz_top40.json', 'trendyol_top20.json', 'trendyol_top40.json', 'PROJE_ANALIZ_README.md']:
    if os.path.exists(fn):
        TARGETS.append(fn)
# data files matching patterns
for pat in [
    'data/trendyol*',
    'data/*page_checked*.json',
    'data/*best_sellers*.json',
    'data/batch_best_sellers',
    'data/trendyol_kadin*'
]:
    for p in glob.glob(pat):
        TARGETS.append(p)
# DB
DB = os.path.join('db','trendyol_products.db')
if os.path.exists(DB):
    TARGETS.append(DB)

if not TARGETS:
    print('No targets found to backup/delete.')
    sys.exit(0)

# create backups dir
bkdir = os.path.join('backups')
os.makedirs(bkdir, exist_ok=True)
stamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
archive = os.path.join(bkdir, f'proje_analiz_google_trends_backup_{stamp}.zip')

print('Backing up the following targets:')
for t in TARGETS:
    print(' -', t)

with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for t in TARGETS:
        if os.path.isdir(t):
            for root, dirs, files in os.walk(t):
                for f in files:
                    full = os.path.join(root, f)
                    arcname = os.path.relpath(full, ROOT)
                    z.write(full, arcname)
        else:
            z.write(t, os.path.relpath(t, ROOT))

print('Backup written to', archive)

# now remove targets
for t in TARGETS:
    try:
        if os.path.isdir(t):
            shutil.rmtree(t)
            print('Removed dir', t)
        else:
            os.remove(t)
            print('Removed file', t)
    except Exception as e:
        print('Failed to remove', t, e)

print('\nCleanup done.')
print('Next: commit changes and push if desired.')
