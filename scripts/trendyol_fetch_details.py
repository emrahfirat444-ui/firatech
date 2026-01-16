#!/usr/bin/env python3
"""Open product URLs from a previous badge-scan and extract title, price and one image.

Usage: python scripts/trendyol_fetch_details.py --cdp http://127.0.0.1:9222 --input data/trendyol_encoksatan_multi_pi.json --out data/trendyol_encoksatan_details.json
"""
import argparse
import json
import time
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def extract_product_info(page):
    # Try meta tags first
    info = page.evaluate("""() => {
        const meta = (name) => {
            const m = document.querySelector('meta[property="' + name + '"]') || document.querySelector('meta[name="' + name + '"]');
            return m ? m.content : null;
        };
        const og_title = meta('og:title') || meta('twitter:title');
        const og_image = meta('og:image') || meta('twitter:image');
        const title_el = document.querySelector('h1') || document.querySelector('[data-testid="product-name"]') || document.querySelector('h2');
        const title_txt = title_el ? title_el.innerText.trim() : (og_title || '');
        // price heuristics
        let price = '';
        const priceSelectors = ['[data-testid="price"]', '.prc', '[class*=price]', '[data-test-id]'];
        for (const s of priceSelectors) {
            const e = document.querySelector(s);
            if (e && e.innerText && /\d/.test(e.innerText)) { price = e.innerText.trim(); break; }
        }
        if (!price) {
            // fallback: find first occurrence of TL in page text
            const body = document.body ? document.body.innerText : '';
            const m = body.match(/\d+[\d.,]*\s*TL/);
            price = m ? m[0] : '';
        }
        return {title: title_txt, price: price, image: og_image};
    }""")
    return info


def download_image(page, url, dest_path: Path):
    try:
        # navigate to image or use fetch in page context
        data = page.evaluate("(url) => fetch(url).then(r=>r.blob()).then(b=>new Promise((res)=>{ const reader = new FileReader(); reader.onload = () => res(reader.result); reader.readAsDataURL(b); }));", url)
        if data and data.startswith('data:'):
            header, b64 = data.split(',', 1)
            import base64
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(base64.b64decode(b64))
            return True
    except Exception:
        pass
    return False


def run(cdp_url, input_file, out_file, max_items=None, delay=1.0):
    inp = Path(input_file)
    outp = Path(out_file)
    if not inp.exists():
        raise SystemExit('Input file not found: ' + input_file)
    entries = json.loads(inp.read_text(encoding='utf-8'))
    results = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        count = 0
        for e in entries:
            if max_items and count >= max_items:
                break
            href = e.get('href')
            if not href:
                continue
            try:
                page.goto(href, wait_until='networkidle', timeout=60000)
            except Exception:
                try:
                    page.goto(href, timeout=60000)
                except Exception:
                    continue
            time.sleep(0.5)
            info = extract_product_info(page)
            # verify badge in product page
            has_badge = page.evaluate("() => { return !!Array.from(document.querySelectorAll('*')).find(n => n.innerText && /en\\s*çok\\s*satan/i.test(n.innerText)); }")
            image_url = info.get('image')
            # if no og:image, try first product gallery image
            if not image_url:
                image_url = page.evaluate("() => { const img = document.querySelector('img[alt]') || document.querySelector('.product-image img'); return img ? img.src : null; }")
            img_saved = None
            if image_url:
                # build filename
                parsed = urlparse(href)
                pid = parsed.path.split('-p-')[-1] if '-p-' in parsed.path else str(abs(hash(href)))
                ext = 'jpg'
                dest = Path('data/images') / f'{pid}.{ext}'
                ok = download_image(page, image_url, dest)
                if ok:
                    img_saved = str(dest)

            result = {
                'href': href,
                'page_title': info.get('title',''),
                'page_price': info.get('price',''),
                'badge_on_page': bool(has_badge),
                'image_url': image_url,
                'image_saved': img_saved,
            }
            results.append(result)
            count += 1
            time.sleep(delay)
        try:
            page.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('WROTE', outp, 'ITEMS', len(results))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cdp', default='http://127.0.0.1:9222')
    parser.add_argument('--input', default='data/trendyol_encoksatan_multi_pi.json')
    parser.add_argument('--out', default='data/trendyol_encoksatan_details.json')
    parser.add_argument('--max', type=int, default=None)
    parser.add_argument('--delay', type=float, default=1.0)
    args = parser.parse_args()
    run(args.cdp, args.input, args.out, max_items=args.max, delay=args.delay)


if __name__ == '__main__':
    main()
