#!/usr/bin/env python3
"""Connect to local Chrome via CDP and scan Trendyol SR pages pi=1..N for 'En Çok Satan' badges.

Usage: python scripts/trendyol_multi_page_scan.py --cdp http://127.0.0.1:9222 --pi-end 10
"""
import argparse
import json
import time
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


def scan(cdp_url, pi_start=1, pi_end=10, wait_between=2.0, max_scrolls=60, out='data/trendyol_encoksatan_multi_pi.json'):
    results = []
    seen = set()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        for pi in range(pi_start, pi_end + 1):
            url = f'https://www.trendyol.com/sr?fl=encoksatanurunler&sst=BEST_SELLER&pi={pi}'
            print('Visiting', url)
            page = ctx.new_page()
            try:
                page.goto(url, wait_until='networkidle', timeout=60000)
            except Exception as e:
                print('goto failed', e)
            prev_count = 0
            stable = 0
            for i in range(max_scrolls):
                # wait for lazy loading
                time.sleep(wait_between)
                # evaluate nodes containing badge text
                try:
                    items = page.evaluate('''() => {
                        const res = [];
                        const nodes = Array.from(document.querySelectorAll('*')).filter(n => n.innerText && /en\s*çok\s*satan/i.test(n.innerText));
                        nodes.forEach(n => {
                            let a = n.closest('a');
                            if(!a) a = n.parentElement && n.parentElement.querySelector('a');
                            if(!a) return;
                            const href = a.href;
                            const title = (a.querySelector('img') && a.querySelector('img').alt) || (a.querySelector('span') && a.querySelector('span').innerText) || a.innerText;
                            const priceEl = a.querySelector('[data-test-id]') || a.querySelector('div[data-testid="price"]') || a.querySelector('[class*=price]') || a.querySelector('div');
                            const price = priceEl ? priceEl.innerText : '';
                            res.push({href, title: title && title.trim(), price: price && price.trim()});
                        });
                        const seen = new Set();
                        return res.filter(r => { if(seen.has(r.href)) return false; seen.add(r.href); return true; });
                    }''')
                except Exception as e:
                    print('evaluate failed', e)
                    items = []

                added = 0
                for it in items:
                    href = it.get('href')
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    results.append({'href': href, 'title': it.get('title',''), 'price': it.get('price',''), 'pi': pi})
                    added += 1

                # scroll down
                try:
                    page.keyboard.press('PageDown')
                except Exception:
                    pass
                # stop if stable for a few iterations
                if added == 0:
                    stable += 1
                    if stable >= 4:
                        break
                else:
                    stable = 0

            try:
                page.close()
            except Exception:
                pass

        try:
            browser.close()
        except Exception:
            pass

    outp = Path(out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('WROTE', outp, 'ITEMS', len(results))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cdp', required=False, default='http://127.0.0.1:9222')
    parser.add_argument('--pi-start', type=int, default=1)
    parser.add_argument('--pi-end', type=int, default=10)
    parser.add_argument('--wait', type=float, default=2.0)
    parser.add_argument('--out', default='data/trendyol_encoksatan_multi_pi.json')
    args = parser.parse_args()
    scan(args.cdp, args.pi_start, args.pi_end, wait_between=args.wait, out=args.out)


if __name__ == '__main__':
    main()
