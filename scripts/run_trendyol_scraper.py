#!/usr/bin/env python
import argparse
import os
import sys
import json

def main():
    parser = argparse.ArgumentParser(description='Run Trendyol scraper in separate process')
    parser.add_argument('--url', required=True, help='Category URL')
    parser.add_argument('--out-dir', default='data', help='Output directory')
    parser.add_argument('--max', type=int, default=200, help='Max products')
    args = parser.parse_args()

    # ensure module path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        from scrapers.trendyol_scraper import scrape_category
    except Exception as e:
        print('ERROR: failed to import scraper:', e, file=sys.stderr)
        sys.exit(2)

    try:
        out_path = scrape_category(args.url, out_dir=args.out_dir, max_products=args.max)
        # normalize path
        out_path = os.path.abspath(out_path) if out_path else ''
        print(out_path)
        sys.stdout.flush()
    except Exception as e:
        print('ERROR: scraper failed:', e, file=sys.stderr)
        sys.exit(3)

if __name__ == '__main__':
    main()
