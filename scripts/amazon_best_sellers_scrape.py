#!/usr/bin/env python3
"""
Simple Amazon Best Sellers scraper inspired by the Trendyol tooling.

Behavior:
- Visit the provided best-sellers landing page (default: https://www.amazon.com.tr/gp/bestsellers)
- Find the left-side category links and iterate them
- For each category: wait ~2s, perform progressive scroll downs to load items,
  collect product links and visit each product to extract title, price, image, breadcrumb
- Save collected items into a JSON details file.

Notes:
- This is implemented with Playwright sync API. It attempts to launch a local headed Chromium.
- For CDP usage you can adapt to connect to an existing browser by editing the launch/connect logic.
"""
import argparse
import json
import os
import time
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


def ensure_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def make_abs(base, href):
    if not href:
        return ''
    if href.startswith('http://') or href.startswith('https://'):
        return href
    return urljoin(base, href)


def scroll_page(page, pause=0.5, steps=12):
    for i in range(steps):
        try:
            page.evaluate("window.scrollBy(0, window.innerHeight);")
        except Exception:
            pass
        time.sleep(pause)


def extract_text_or_empty(el):
    try:
        if not el:
            return ''
        return el.inner_text().strip()
    except Exception:
        try:
            return el.text_content().strip()
        except Exception:
            return ''


def scrape(best_url, output_file, headless=False, max_products_per_category=60):
    items = []
    ensure_dir(output_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        page.goto(best_url, timeout=30000)
        time.sleep(2)

        # heuristics to find left-side category anchors
        selectors = [
            '#zg_browseRoot a',
            'div#zg_browseRoot a',
            'div.browseNode a',
            'ul.a-unordered-list a',
            'div._p13n-zg-nav-tree-all_style_zg-browse-all_1L2F8 a'
        ]

        cat_anchors = []
        for sel in selectors:
            try:
                els = page.query_selector_all(sel)
                if els:
                    for e in els:
                        h = e.get_attribute('href') or ''
                        t = extract_text_or_empty(e)
                        if h and t:
                            cat_anchors.append((t, make_abs(best_url, h)))
                    if cat_anchors:
                        break
            except Exception:
                continue

        # fallback: find any sidebar link to bestsellers subpages
        if not cat_anchors:
            try:
                els = page.query_selector_all('a[href*="/gp/bestsellers/"]')
                for e in els:
                    h = e.get_attribute('href') or ''
                    t = extract_text_or_empty(e)
                    if h and t:
                        cat_anchors.append((t, make_abs(best_url, h)))
            except Exception:
                pass

        # de-duplicate categories while preserving order
        seen = set()
        categories = []
        for t, u in cat_anchors:
            key = u
            if key and key not in seen:
                seen.add(key)
                categories.append((t, u))

        print(f"Found {len(categories)} categories to scan")

        for cat_name, cat_url in categories:
            try:
                print(f"Scanning category: {cat_name} -> {cat_url}")
                page.goto(cat_url, timeout=30000)
                time.sleep(2)
                scroll_page(page, pause=0.5, steps=8)

                # collect product links
                product_els = page.query_selector_all('a[href*="/dp/"]')
                prod_hrefs = []
                for pe in product_els:
                    h = pe.get_attribute('href') or ''
                    if h:
                        full = make_abs(cat_url, h.split('?')[0])
                        prod_hrefs.append(full)

                # dedupe and limit
                unique = []
                seenp = set()
                for u in prod_hrefs:
                    if u and u not in seenp:
                        seenp.add(u)
                        unique.append(u)
                    if len(unique) >= max_products_per_category:
                        break

                print(f"  Found {len(unique)} product links (capped at {max_products_per_category})")

                for prod_link in unique:
                    try:
                        print(f"    Visiting product: {prod_link}")
                        prod_page = context.new_page()
                        prod_page.goto(prod_link, timeout=30000)
                        prod_page.wait_for_load_state('networkidle', timeout=10000)
                        time.sleep(1)

                        title_el = prod_page.query_selector('#productTitle') or prod_page.query_selector('h1')
                        title = extract_text_or_empty(title_el)

                        price_el = prod_page.query_selector('#priceblock_ourprice') or prod_page.query_selector('#priceblock_dealprice') or prod_page.query_selector('span.a-price > span.a-offscreen')
                        price = extract_text_or_empty(price_el)

                        # image
                        img = ''
                        try:
                            meta = prod_page.query_selector('meta[property="og:image"]')
                            if meta:
                                img = meta.get_attribute('content') or ''
                        except Exception:
                            pass
                        if not img:
                            imel = prod_page.query_selector('#landingImage') or prod_page.query_selector('#imgTagWrapperId img') or prod_page.query_selector('img[data-old-hires]')
                            if imel:
                                img = imel.get_attribute('src') or imel.get_attribute('data-old-hires') or ''

                        # breadcrumb -> category_3 (third breadcrumb entry if present)
                        cat3 = ''
                        try:
                            crumbs = prod_page.query_selector_all('#wayfinding-breadcrumbs_container li a')
                            texts = [extract_text_or_empty(c) for c in crumbs]
                            texts = [t for t in texts if t]
                            if len(texts) >= 3:
                                cat3 = texts[2]
                            elif texts:
                                cat3 = texts[-1]
                        except Exception:
                            cat3 = ''

                        # badge detection
                        page_text = prod_page.content().lower()
                        badge_on_page = ('en çok satan' in page_text) or ('best seller' in page_text)

                        item = {
                            'page_title': title,
                            'page_price': price,
                            'image_url': img,
                            'image_saved': '',
                            'href': prod_link,
                            'category_3': cat3,
                            'badge_on_page': bool(badge_on_page),
                            'scraped_category': cat_name,
                        }
                        items.append(item)
                        try:
                            prod_page.close()
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"      Product visit failed: {e}")
                        continue

            except Exception as e:
                print(f"  Category scan failed: {e}")
                continue

        try:
            browser.close()
        except Exception:
            pass

    # write output
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"WROTE {output_file} ITEMS {len(items)}")
    except Exception as e:
        print(f"Failed to write output: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', '-u', default='https://www.amazon.com.tr/gp/bestsellers', help='Best sellers landing URL')
    parser.add_argument('--output', '-o', default='data/amazon_encoksatan_details.json', help='Output JSON file')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--max-per-cat', type=int, default=60, help='Max products per category')
    args = parser.parse_args()

    scrape(args.url, args.output, headless=args.headless, max_products_per_category=args.max_per_cat)


if __name__ == '__main__':
    main()
