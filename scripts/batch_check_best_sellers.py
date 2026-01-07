#!/usr/bin/env python
"""
Batch runner for check_best_seller_by_page.py across multiple Trendyol categories.
Runs the page checker for each category, collects results, and merges into a unified JSON.
"""
import subprocess
import json
import os
from pathlib import Path

# Define categories to scan
CATEGORIES = [
    {
        'name': 'kadin',
        'url': 'https://www.trendyol.com/kadin',
        'max_products': 50
    },
    {
        'name': 'erkek',
        'url': 'https://www.trendyol.com/erkek',
        'max_products': 50
    },
    {
        'name': 'cocuk',
        'url': 'https://www.trendyol.com/cocuk',
        'max_products': 50
    },
    {
        'name': 'ev-yasam',
        'url': 'https://www.trendyol.com/ev-yasam',
        'max_products': 50
    },
    {
        'name': 'elektronik',
        'url': 'https://www.trendyol.com/elektronik',
        'max_products': 50
    }
]

OUT_DIR = Path('data/batch_best_sellers')
OUT_UNIFIED = Path('data/trendyol_best_sellers_unified.json')
OUT_TOP40 = Path('trendyol_top40.json')

def run():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    python_bin = os.path.join(os.getcwd(), '.venv', 'Scripts', 'python.exe')
    if not os.path.exists(python_bin):
        python_bin = 'python'
    
    all_results = []
    
    for cat in CATEGORIES:
        print(f"\n{'='*60}")
        print(f"Processing category: {cat['name']}")
        print(f"URL: {cat['url']}")
        print(f"Max products: {cat['max_products']}")
        print('='*60)
        
        out_raw = OUT_DIR / f"{cat['name']}_page_checked.json"
        out_top20 = OUT_DIR / f"{cat['name']}_top20.json"
        
        cmd = [
            python_bin,
            'scripts/check_best_seller_by_page.py',
            '--category-url', cat['url'],
            '--max-products', str(cat['max_products']),
            '--out-raw', str(out_raw),
            '--out-top20', str(out_top20)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            print(result.stdout)
            if result.stderr:
                print('STDERR:', result.stderr)
            
            # Load results
            if out_raw.exists():
                with open(out_raw, 'r', encoding='utf-8') as f:
                    cat_results = json.load(f)
                    # Tag with category
                    for item in cat_results:
                        item['category'] = cat['name']
                        item['category_url'] = cat['url']
                    all_results.extend(cat_results)
                    print(f"[OK] Loaded {len(cat_results)} results from {cat['name']}")
        except subprocess.TimeoutExpired:
            print(f"[TIMEOUT] Category {cat['name']}")
        except Exception as e:
            print(f"[ERROR] Category {cat['name']}: {e}")
    
    # Write unified results
    print(f"\n{'='*60}")
    print(f"Writing unified results: {len(all_results)} total items")
    print('='*60)
    
    with open(OUT_UNIFIED, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    # Write top 40
    top40 = all_results[:40]
    with open(OUT_TOP40, 'w', encoding='utf-8') as f:
        json.dump(top40, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] Wrote {OUT_UNIFIED} ({len(all_results)} items)")
    print(f"[OK] Wrote {OUT_TOP40} ({len(top40)} items)")
    
    # Print summary by category
    print(f"\n{'='*60}")
    print("Summary by category:")
    print('='*60)
    cat_counts = {}
    for item in all_results:
        cat_name = item.get('category', 'unknown')
        cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1
    
    for cat_name, count in sorted(cat_counts.items()):
        print(f"  {cat_name:20s}: {count:3d} products")
    
    print(f"\nTotal: {len(all_results)} best-seller products found")

if __name__ == '__main__':
    run()
