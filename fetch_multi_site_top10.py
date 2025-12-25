from playwright.sync_api import sync_playwright
import requests
import json
import os
import time
import re
import glob

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, 'proje_analiz_top40.json')

sites = [
    {'name':'trendyol','url':'https://www.trendyol.com','search':'https://www.trendyol.com/sr?q=yatak'},
    {'name':'amazon','url':'https://www.amazon.com.tr/gp/bestsellers','search':'https://www.amazon.com.tr/gp/bestsellers'},
    {'name':'hepsiburada','url':'https://www.hepsiburada.com/cok-satanlar','search':'https://www.hepsiburada.com/cok-satanlar'},
    {'name':'n11','url':'https://www.n11.com/','search':'https://www.n11.com/arama?q=yatak'}
]

PRICE_RE = re.compile(r"([0-9]{1,3}(?:[\.,][0-9]{3})*(?:[\.,][0-9]{2})?)")


def extract_candidates_from_page(page, site_name):
    # site-specific heuristics: prefer product anchors/data attributes
    els = []
    try:
        if site_name == 'n11':
            # n11 often marks product tiles with data-product-id attributes
            els = page.query_selector_all('[data-product-id]')
            if not els:
                els = page.query_selector_all('a')
        elif site_name == 'hepsiburada':
            # hepsiburada product urls often contain '-p-'
            els = page.query_selector_all("a[href*='-p-']")
            if not els:
                els = page.query_selector_all('a')
        elif site_name == 'amazon':
            # amazon product links often include '/dp/' or '/gp/'
            els = page.query_selector_all("a[href*='/dp/'], a[href*='/gp/']")
            if not els:
                els = page.query_selector_all('a')
        else:
            els = page.query_selector_all('a')
    except Exception:
        els = page.query_selector_all('a')
    items = []
    seen = set()
    for a in els:
        try:
            # some matches may be container elements; prefer an inner anchor if present
            href = a.get_attribute('href') or ''
            if href.startswith('#'):
                continue
            img = a.query_selector('img')
            if not img:
                # try parent
                try:
                    p = a.evaluate_handle('el => el.parentElement')
                    if p:
                        img = p.query_selector('img')
                except Exception:
                    img = None
            if not img:
                continue
            src = img.get_attribute('src') or img.get_attribute('data-src') or ''
            # find title text nearby
            title = (a.inner_text() or '').strip()
            if not title:
                # try alt
                title = img.get_attribute('alt') or ''
            # for n11 tiles the element may be a container with category name; try data-title or aria-label
            if site_name == 'n11' and (not title or title.strip()==''):
                title = a.get_attribute('data-title') or a.get_attribute('aria-label') or title
            # find price in parent element
            price = None
            parent = a
            for depth in range(3):
                txt = parent.inner_text() or ''
                m = PRICE_RE.search(txt)
                if m:
                    raw = m.group(1)
                    try:
                        price = float(raw.replace('.', '').replace(',', '.'))
                        break
                    except:
                        pass
                # climb
                try:
                    parent = parent.evaluate_handle('el => el.parentElement')
                except Exception:
                    break
            # normalize url
            if href and href.startswith('/'):
                url = page.url.split('//')[0] + '//' + page.url.split('//')[1].split('/')[0] + href
            elif href.startswith('http'):
                url = href
            else:
                url = (page.url.rstrip('/') + '/' + href.lstrip('/')) if href else page.url
            # ensure product-like url for some sites
            if site_name == 'n11':
                # prefer product URLs (contain '/product' or '/urun' or '/p/')
                if not re.search(r'(/product|/urun|-p-)', url, re.I):
                    # skip pure category links
                    # allow some fallback but mark empty title
                    pass
            key = (title or src or url)[:200]
            if not title and not src:
                continue
            if key in seen:
                continue
            seen.add(key)
            items.append({'site':site_name,'product_name':title,'price':price,'image_url':src,'url':url})
        except Exception:
            continue
    # For n11 prefer product-detail urls (they usually include '/urun/')
    if site_name == 'n11':
        prod_like = []
        for it in items:
            u = it.get('url') or ''
            if re.search(r'/urun/|/urun-|/product|/urun', u, re.I):
                prod_like.append(it)
        if prod_like:
            return prod_like
    return items


def run_all():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        page = ctx.new_page()
        for s in sites:
            print('Visiting', s['name'], s['search'])
            try:
                # For n11 prefer its JSON search endpoint which includes productListingItems
                if s['name'] == 'n11':
                    # 1) Try n11 JSON search endpoint from browser context
                    prods = []
                    try:
                        api_url = s['search'] + ('&' if '?' in s['search'] else '?') + 'vueSearch=1&pg=1'
                        resp = page.request.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15000)
                        j = resp.json()
                        prods = j.get('data', {}).get('productListingItems') or j.get('productListingItems') or []
                    except Exception:
                        prods = []

                    # 2) If JSON failed or returned categories, fall back to DOM extraction (which prefers /urun/ links)
                    if not prods:
                        try:
                            page.goto(s['search'], wait_until='networkidle', timeout=30000)
                        except Exception:
                            try:
                                page.goto(s['search'], timeout=30000)
                            except Exception:
                                pass
                        time.sleep(1)
                        items_dom = extract_candidates_from_page(page, 'n11')
                        if items_dom:
                            results.extend(items_dom[:12])
                            continue

                    # 3) If we have JSON products, use them
                    if prods:
                        items = []
                        for pitem in prods:
                            title = pitem.get('title') or pitem.get('name') or pitem.get('brand') or ''
                            img = None
                            imgs = pitem.get('imagePathList') or pitem.get('imagePath') or []
                            if isinstance(imgs, list) and len(imgs) > 0:
                                img = imgs[0].replace('{0}', '')
                            url_part = pitem.get('urlWithoutSellerShop') or pitem.get('url') or ''
                            url = 'https://www.n11.com' + url_part if url_part.startswith('/') else url_part
                            price = pitem.get('advantageDeliveryPrice') or pitem.get('firstMinFinalPriceForFourteenDay') or pitem.get('firstMinFinalPriceForThirtyDay') or None
                            try:
                                if price is not None:
                                    price = float(price)
                            except Exception:
                                price = None
                            items.append({'site': 'n11', 'product_name': title, 'price': price, 'image_url': img, 'url': url})
                        results.extend(items[:12])
                        continue
                page.goto(s['search'], wait_until='networkidle', timeout=30000)
            except Exception:
                try:
                    page.goto(s['search'], timeout=30000)
                except Exception:
                    continue
            time.sleep(1)
            items = extract_candidates_from_page(page, s['name'])
            # If N11 returned category tiles (titles short, urls look like categories),
            # visit top categories and try extracting product anchors from those pages.
            if s['name'] == 'n11':
                cat_like = [it for it in items if it.get('url') and any(x in it.get('url') for x in ['/giyim','/ayakkabi','/elektronik','/urun','/telefon','/cocuk','/ev'])]
                if len(cat_like) >= 6:
                    expanded = []
                    for c in cat_like[:6]:
                        try:
                            page.goto(c['url'], wait_until='networkidle', timeout=30000)
                            time.sleep(1)
                            more = extract_candidates_from_page(page, 'n11')
                            expanded.extend(more)
                            if len(expanded) >= 12:
                                break
                        except Exception:
                            continue
                    if expanded:
                        items = expanded
            # take first 12 heuristically to ensure we can dedupe later
            results.extend(items[:12])
        # dedupe by product_name+site
        final = []
        seen = set()
        for it in results:
            key = (it.get('site','') + '|' + (it.get('product_name') or '')[:200])
            if key in seen:
                continue
            seen.add(key)
            final.append(it)

        # Enrich N11 entries: if product_name is empty or looks like a category,
        # visit product page and try to extract a descriptive H1/title.
        category_words = set(['Moda','Ayakkabi','Ayakkabı','Çanta','Giyim','Kozmetik','Elektronik','Ev','Mobilya','Aksesuar','Çocuk','Kadın','Erkek'])
        for itm in final:
            if itm.get('site') != 'n11':
                continue
            title = (itm.get('product_name') or '').strip()
            needs = False
            if not title:
                needs = True
            else:
                # detect short/category-like titles
                tnorm = title.replace('&',' ').split()
                if len(title) < 6 or any(w.lower() in ' '.join(tnorm).lower() for w in [cw.lower() for cw in category_words]):
                    needs = True
            if not needs:
                continue
            url = itm.get('url') or ''
            if not url or not url.startswith('http'):
                continue
            try:
                print('Enriching n11 item from', url)
                page.goto(url, wait_until='networkidle', timeout=15000)
                # try common title selectors
                h1 = None
                try:
                    h1 = page.query_selector('h1')
                except Exception:
                    h1 = None
                newtitle = ''
                if h1:
                    try:
                        newtitle = (h1.inner_text() or '').strip()
                    except Exception:
                        newtitle = ''
                if not newtitle:
                    try:
                        newtitle = page.title() or ''
                    except Exception:
                        newtitle = ''
                if newtitle:
                    # discard if still category-like
                    if not any(cw.lower() in newtitle.lower() for cw in category_words):
                        itm['product_name'] = newtitle
            except Exception:
                continue
        browser.close()
    # ensure 10 per site if possible; fill missing by repeating
    out = []
    for s in [x['name'] for x in sites]:
        group = [i for i in final if i['site']==s]
        needed = 10
        for g in group[:needed]:
            out.append(g)
        # if not enough, pad with available across all
        if len(group) < needed:
            # add from others not same site
            extra = [i for i in final if i['site']!=s]
            idx = 0
            while len(group) + idx < needed and idx < len(extra):
                out.append(extra[idx])
                idx += 1
    # if still less than 40, trim/extend
    if len(out) < 40:
        # append more from final
        for i in final:
            if len(out) >= 40:
                break
            if i not in out:
                out.append(i)
    out = out[:40]
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('Wrote', OUT, 'items_count=', len(out))

if __name__ == '__main__':
    run_all()
