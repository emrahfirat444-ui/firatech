#!/usr/bin/env python3
"""Scrape Trendyol "En Çok Satan" badges from a given SR search page.

Usage: python scripts/trendyol_best_sellers_scrape.py --url <URL> --output <output.json>
"""
import argparse
import json
import time
import re
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    raise SystemExit("Playwright is required. Install with: pip install playwright && playwright install")


def normalize_price(text: str):
    if not text:
        return None
    nums = re.findall(r"\d+[\d.,]*", text.replace('\n',' '))
    if not nums:
        return None
    # pick the first numeric group and strip non-digit
    p = nums[0]
    p = p.replace('.', '').replace(',', '.')
    try:
        return float(p)
    except Exception:
        return None


def scrape(url, out_path, max_scrolls=60, wait_between=0.6, cdp_url=None):
    results = []
    seen = set()
    out_path = Path(out_path)
    with sync_playwright() as p:
        browser = None
        context = None
        page = None

        if cdp_url:
            try:
                browser = p.chromium.connect_over_cdp(cdp_url)
                if browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = browser.new_context(
                        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                        locale='tr-TR',
                        viewport={"width": 1200, "height": 900},
                    )
                page = context.new_page()
                page.set_extra_http_headers({"accept-language": "tr-TR,tr;q=0.9"})
                page.goto(url, timeout=60000, wait_until='networkidle')
            except Exception as e:
                print(f'CDP connect failed: {e}')
                browser = None

        if not browser:
            browser = p.chromium.launch(headless=False, args=['--no-sandbox'])
            context = browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                locale='tr-TR',
                viewport={"width": 1200, "height": 900},
            )
            page = context.new_page()
            page.set_extra_http_headers({"accept-language": "tr-TR,tr;q=0.9"})
            page.goto(url, timeout=60000, wait_until='networkidle')

        prev_count = 0
        for i in range(max_scrolls):
            # wait for lazy-loaded content
            time.sleep(wait_between)

            # evaluate page anchors and return their HTML/text to Python
            try:
                anchors = page.evaluate(
                    """() => {
                        const results = [];
                        const re = /en\s*çok\s*satan/i;
                        // Walk the document and find elements whose visible text matches the badge
                        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, {
                            acceptNode: function(node) {
                                try {
                                    const txt = (node.innerText || '').trim();
                                    return re.test(txt) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                                } catch(e) { return NodeFilter.FILTER_REJECT; }
                            }
                        });
                        const seen = new Set();
                        let n = walker.nextNode();
                        while (n) {
                            try {
                                const a = n.closest('a[href*="/p/"]');
                                if (a && a.href && !seen.has(a.href)) {
                                    seen.add(a.href);
                                    results.push({href: a.href, html: a.innerHTML || '', text: a.innerText || ''});
                                }
                            } catch(e) {}
                            n = walker.nextNode();
                        }
                        return results;
                    }"""
                )
            except Exception:
                anchors = []

            for a in anchors:
                try:
                    html = (a.get('html') or '')
                    text = (a.get('text') or '')
                    href = a.get('href')
                    if not href or href in seen:
                        continue

                    # match 'En Çok Satan' anywhere in the anchor's html/text (case-insensitive)
                    if re.search(r"en\s*çok\s*satan", html, flags=re.I | re.U) or re.search(r"en\s*çok\s*satan", text, flags=re.I | re.U):
                        # try to extract title from text (line before price) or from html tag alt
                        title = text.strip().split('\n')[0].strip()
                        # try to find first numeric price in html/text
                        price_match = re.search(r"\d+[\d.,]*\s*TL", html) or re.search(r"\d+[\d.,]*\s*TL", text)
                        price_text = price_match.group(0) if price_match else ''
                        price = normalize_price(price_text)
                        seen.add(href)
                        results.append({
                            'title': title,
                            'price_text': price_text,
                            'price': price,
                            'url': href,
                        })
                except Exception:
                    continue

            # scroll down a bit to load more products
            try:
                page.keyboard.press('PageDown')
            except Exception:
                pass
            time.sleep(wait_between)

            # stop early if no new items for several iterations
            if len(seen) == prev_count:
                stable = getattr(page, '_stable_count', 0) + 1
                page._stable_count = stable
                if stable >= 4:
                    break
            else:
                page._stable_count = 0
            prev_count = len(seen)

        try:
            browser.close()
        except Exception:
            pass

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'Wrote {out_path} ({len(results)} items)')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=False, default='https://www.trendyol.com/sr?fl=encoksatanurunler&sst=BEST_SELLER&pi=4')
    parser.add_argument('--output', required=False, default='data/trendyol_encoksatan_results.json')
    parser.add_argument('--cdp-url', required=False, default=None, help='Chrome DevTools Protocol URL (e.g. http://127.0.0.1:9222) to connect to an existing browser')
    args = parser.parse_args()
    scrape(args.url, args.output, cdp_url=args.cdp_url)


if __name__ == '__main__':
    main()
