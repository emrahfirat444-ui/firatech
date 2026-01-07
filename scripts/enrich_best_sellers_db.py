#!/usr/bin/env python
"""
Enrich unified best-sellers JSON with category_3 breadcrumbs and write to DB.
Reads data/trendyol_best_sellers_unified.json, visits product pages to extract
breadcrumbs, updates the JSON, and writes to db/trendyol_products.db.
"""
from playwright.sync_api import sync_playwright
import json, time, sqlite3, os, re
from pathlib import Path

IN_JSON = Path('data/trendyol_best_sellers_unified.json')
OUT_JSON = Path('data/trendyol_best_sellers_enriched.json')
DB_PATH = Path('db/trendyol_products.db')

def extract_breadcrumbs(page, url):
    """Extract category_3 from product page breadcrumb."""
    try:
        page.goto(url, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(0.4)
    except Exception as e:
        print(f'  [ERROR] Page load: {e}')
        return None
    
    # Try multiple breadcrumb selectors
    breadcrumb_variants = [
        'nav[role="navigation"] a',
        '[class*="breadcrumb"] a',
        'nav a',
        'ol[itemtype*="BreadcrumbList"] a',
    ]
    
    for sel in breadcrumb_variants:
        try:
            links = page.query_selector_all(sel)
            if links and len(links) >= 3:
                # Get the 3rd breadcrumb (usually category level 3)
                try:
                    text = links[2].inner_text().strip()
                    if text and len(text) > 2:
                        return text
                except Exception:
                    continue
        except Exception:
            continue
    
    # Fallback: search for any nav text
    try:
        nav = page.locator('nav').nth(0).inner_text()
        parts = [p.strip() for p in nav.split('>') if p.strip()]
        if len(parts) >= 3:
            return parts[2]
    except Exception:
        pass
    
    return None

def init_db():
    """Initialize SQLite database."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_url TEXT PRIMARY KEY,
            product_name TEXT,
            image_url TEXT,
            price REAL,
            category TEXT,
            category_url TEXT,
            category_3 TEXT,
            badge_reason TEXT,
            badge_text TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def write_to_db(conn, items):
    """Write items to database."""
    c = conn.cursor()
    for item in items:
        reason = item.get('reason', {})
        badge_reason = reason.get('reason') if isinstance(reason, dict) else None
        badge_text = reason.get('badge_text') if isinstance(reason, dict) else None
        
        c.execute('''
            INSERT OR REPLACE INTO products 
            (product_url, product_name, image_url, price, category, category_url, 
             category_3, badge_reason, badge_text, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            item.get('product_url'),
            item.get('product_name'),
            item.get('image_url'),
            item.get('price'),
            item.get('category'),
            item.get('category_url'),
            item.get('category_3'),
            badge_reason,
            badge_text
        ))
    conn.commit()

def run():
    if not IN_JSON.exists():
        print(f'[ERROR] Input file not found: {IN_JSON}')
        return
    
    with open(IN_JSON, 'r', encoding='utf-8') as f:
        items = json.load(f)
    
    print(f'Loaded {len(items)} items from {IN_JSON}')
    print('Extracting category_3 breadcrumbs...\n')
    
    updated = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        
        for i, item in enumerate(items, start=1):
            url = item.get('product_url')
            if not url:
                continue
            
            # Skip if already has category_3
            if item.get('category_3'):
                print(f'{i}/{len(items)} SKIP (has cat3): {item.get("product_name", "")[:60]}')
                continue
            
            print(f'{i}/{len(items)} {item.get("product_name", "")[:60]}')
            cat3 = extract_breadcrumbs(page, url)
            if cat3:
                item['category_3'] = cat3
                updated += 1
                print(f'  -> category_3: {cat3}')
            else:
                print(f'  -> category_3: (not found)')
            
            time.sleep(0.4)
        
        browser.close()
    
    print(f'\n{"="*60}')
    print(f'Updated {updated}/{len(items)} items with category_3')
    print('='*60)
    
    # Write enriched JSON
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f'[OK] Wrote {OUT_JSON}')
    
    # Write to DB
    conn = init_db()
    write_to_db(conn, items)
    conn.close()
    print(f'[OK] Wrote {len(items)} records to {DB_PATH}')
    
    # Update top40
    top40 = items[:40]
    top40_path = Path('trendyol_top40.json')
    with open(top40_path, 'w', encoding='utf-8') as f:
        json.dump(top40, f, ensure_ascii=False, indent=2)
    print(f'[OK] Updated {top40_path} with {len(top40)} items')

if __name__ == '__main__':
    run()
