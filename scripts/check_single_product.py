#!/usr/bin/env python
"""Open a single product URL and print best-seller badge detection details."""
from playwright.sync_api import sync_playwright
import sys, json, time

def looks_like_best(text: str):
    if not text:
        return False
    for t in ['En Çok Satan', 'En Çok', 'Çok Satan', 'Çok satan', 'En çok']:
        if t.lower() in text.lower():
            return True
    return False

def check(url: str):
    out = {'url': url, 'found': False, 'reasons': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1200,'height':900})
        try:
            page.goto(url, timeout=30000)
            page.wait_for_load_state('networkidle', timeout=10000)
            time.sleep(0.5)
        except Exception as e:
            out['reasons'].append({'error': f'load_failed: {e}'})
            browser.close()
            return out

        # direct text locator
        try:
            if page.locator('text=/En\\s*Çok\\s*Satan/i').count() > 0 or page.locator('text="En Çok Satan"').count() > 0:
                out['found'] = True
                out['reasons'].append({'method': 'text-locator'})
        except Exception:
            pass

        # badge selectors
        try:
            badge_selectors = ['[class*="badge"]', '[class*="rozet"]', '[class*="ribbon"]', '.badge', '.rozet', '.ribbon', '[data-badge]']
            for sel in badge_selectors:
                try:
                    els = page.query_selector_all(sel)
                    for e in els:
                        try:
                            txt = e.inner_text() or ''
                            if looks_like_best(txt):
                                out['found'] = True
                                out['reasons'].append({'method': f'badge-{sel}', 'text': txt.strip()})
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass

        # body text scan
        try:
            body = page.locator('body').inner_text()
            if looks_like_best(body):
                out['found'] = True
                out['reasons'].append({'method': 'body-text'})
        except Exception:
            pass

        # json-ld scan
        try:
            sds = page.query_selector_all('script[type="application/ld+json"]')
            for i in range(min(10, len(sds))):
                try:
                    txt = sds[i].inner_text()
                    j = json.loads(txt)
                    sj = json.dumps(j, ensure_ascii=False).lower()
                    for t in ['en çok satan', 'çok satan', 'en çok ziyaret', 'en çok ziyaret edilen']:
                        if t in sj:
                            out['found'] = True
                            out['reasons'].append({'method': 'json-ld', 'snippet': t})
                except Exception:
                    continue
        except Exception:
            pass

        browser.close()
    return out

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: check_single_product.py <product_url>')
        sys.exit(2)
    url = sys.argv[1]
    res = check(url)
    print(json.dumps(res, ensure_ascii=False, indent=2))
