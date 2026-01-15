from playwright.sync_api import sync_playwright
import time
import json
from pathlib import Path
import re


def _extract_price_from_text(text: str):
    if not text:
        return None
    # find patterns like 1.234,56 TL or 1234 TL
    m = re.search(r'([0-9\.,]+)\s*(TL|₺)', text)
    if m:
        s = m.group(1)
        s = s.replace('.', '').replace(',', '.')
        try:
            return float(s)
        except Exception:
            return None
    # fallback: find first plain number with at least 2 digits
    m2 = re.search(r'([0-9]{2,}[\.,]?[0-9]*)', text)
    if m2:
        try:
            return float(m2.group(1).replace('.', '').replace(',', '.'))
        except Exception:
            return None
    return None


def scrape_category(category_url: str, out_dir: str = '.', max_products: int = 200):
    out = []
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(category_url, timeout=30000)
        time.sleep(2)

        # try to open sort dropdown and explicitly select "En Çok Satan"
        try:
            # If the literal control is visible, click it directly
            if page.locator("text=En Çok Satan").count() > 0:
                try:
                    page.locator("text=En Çok Satan").first.click()
                    page.wait_for_load_state('networkidle', timeout=5000)
                    time.sleep(0.8)
                except Exception:
                    pass
            else:
                # Try a set of likely sort-trigger selectors and then look for the menu item
                triggers = ['button[aria-label*="Sırala"]', 'button[aria-label*="Sıralama"]', 'button[class*=sort]', 'div.sorter', '[data-test="sortBy"]', 'button']
                for sel in triggers:
                    try:
                        els = page.locator(sel)
                        cnt = els.count()
                        for i in range(min(cnt, 6)):
                            try:
                                els.nth(i).click()
                                time.sleep(0.5)
                                # after opening, try to click the exact menu item by text or regex
                                if page.locator('text=/En\\s*Çok\\s*Satan/i').count() > 0:
                                    try:
                                        page.locator('text=/En\\s*Çok\\s*Satan/i').first.click()
                                        page.wait_for_load_state('networkidle', timeout=5000)
                                        time.sleep(0.8)
                                    except Exception:
                                        pass
                                    break
                                # sometimes options are list items; try to scan nearby list entries
                                menu_items = page.locator('ul li, div[role="menu"] li, div[role="listbox"] li, .sort-list li, .sort-options li')
                                if menu_items.count() > 0:
                                    for j in range(menu_items.count()):
                                        try:
                                            txt = menu_items.nth(j).inner_text()
                                            if txt and re.search(r'En\s*Çok\s*Satan', txt, re.I):
                                                try:
                                                    menu_items.nth(j).click()
                                                    page.wait_for_load_state('networkidle', timeout=5000)
                                                    time.sleep(0.8)
                                                except Exception:
                                                    pass
                                                break
                                        except Exception:
                                            continue
                            except Exception:
                                continue
                        # if we found the menu item text visible now, stop trying other triggers
                        if page.locator('text=/En\\s*Çok\\s*Satan/i').count() > 0:
                            break
                    except Exception:
                        continue

            # small wait to let sort apply
            time.sleep(1.2)

            # Extra attempt: directly search for any visible element that matches the label regex
            try:
                candidate = page.locator('text=/En\\s*Çok\\s*Satan/i')
                if candidate.count() > 0:
                    try:
                        candidate.first.click()
                        page.wait_for_load_state('networkidle', timeout=7000)
                        time.sleep(0.8)
                    except Exception:
                        pass
            except Exception:
                pass

            # Fallback: if page exposes a 'cok-satanlar' (best-seller) quick link, follow it
            try:
                best_link = None
                loc = page.locator('a[href*="cok-satanlar"], a[href*="bestSeller"]')
                if loc.count() > 0:
                    href = loc.nth(0).get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            href = 'https://www.trendyol.com' + href
                        best_link = href
                if best_link:
                    try:
                        page.goto(best_link, timeout=30000)
                        page.wait_for_load_state('networkidle', timeout=10000)
                        time.sleep(1.0)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

        # infinite scroll until no new items
        prev_count = 0
        for _ in range(60):
            page.evaluate('window.scrollBy(0, document.body.scrollHeight)')
            time.sleep(0.8)
            links = page.locator('a[href*="/p/"]')
            cur = links.count()
            if cur >= max_products:
                break
            if cur == prev_count:
                # no change after scroll, break
                break
            prev_count = cur

        # collect unique product hrefs preserving page order, prefer anchors inside product-card containers
        card_containers = ['div.p-card', 'div.product-card', '.p-card', 'div[data-testid="product-card"]', 'li.product-item', 'div.prd']
        seen = set()
        hrefs = []
        for cont in card_containers:
            try:
                loc = page.locator(f'{cont} a[href*="/p/"]')
                if loc.count() < 1:
                    continue
                for i in range(loc.count()):
                    try:
                        h = loc.nth(i).get_attribute('href')
                    except Exception:
                        h = None
                    if not h:
                        continue
                    if h.startswith('/'):
                        h = 'https://www.trendyol.com' + h
                    if h in seen:
                        continue
                    seen.add(h)
                    hrefs.append(h)
                    if len(hrefs) >= max_products:
                        break
                if hrefs:
                    break
            except Exception:
                continue

        # fallback: any anchor with /p/ if container-based selection failed
        if not hrefs:
            loc = page.locator('a[href*="/p/"]')
            for i in range(loc.count()):
                try:
                    h = loc.nth(i).get_attribute('href')
                except Exception:
                    h = None
                if not h:
                    continue
                if h.startswith('/'):
                    h = 'https://www.trendyol.com' + h
                if h in seen:
                    continue
                seen.add(h)
                hrefs.append(h)
                if len(hrefs) >= max_products:
                    break

        # visit each product and extract details
        for idx, h in enumerate(hrefs, start=1):
            try:
                prod_page = browser.new_page()
                prod_page.goto(h, timeout=20000)
                prod_page.wait_for_load_state('networkidle', timeout=8000)
                time.sleep(0.6)
                body = prod_page.evaluate('() => document.body.innerText')

                # title and image and breadcrumb (robust extraction)
                title = None
                image_url = None
                third = None

                # title
                try:
                    for tsel in ['h1', '.pr-new-br', '.product-name', 'h1.pr-header__title', '.product-detail-title', '[data-testid="product-name"]', '.product-title']:
                        try:
                            el = prod_page.locator(tsel)
                            if el.count() > 0:
                                title = el.nth(0).inner_text().strip()
                                if title:
                                    break
                        except Exception:
                            continue
                except Exception:
                    title = None

                # image: try JSON-LD, og:image, link rel, then visible imgs
                try:
                    # 1) JSON-LD
                    try:
                        ld = prod_page.locator('script[type="application/ld+json"]')
                        for i in range(min(ld.count(), 6)):
                            try:
                                txt = ld.nth(i).inner_text()
                                import json as _json
                                doc = _json.loads(txt)
                                if isinstance(doc, dict) and doc.get('image'):
                                    iv = doc.get('image')
                                    image_url = iv[0] if isinstance(iv, list) else iv
                                    break
                                if isinstance(doc, list):
                                    for item in doc:
                                        if isinstance(item, dict) and item.get('image'):
                                            iv = item.get('image')
                                            image_url = iv[0] if isinstance(iv, list) else iv
                                            break
                                    if image_url:
                                        break
                            except Exception:
                                continue
                        if image_url and image_url.startswith('//'):
                            image_url = 'https:' + image_url
                    except Exception:
                        pass

                    # 2) og:image
                    if not image_url:
                        try:
                            meta = prod_page.locator('meta[property="og:image"]')
                            if meta.count() > 0:
                                v = meta.nth(0).get_attribute('content')
                                if v:
                                    image_url = v
                        except Exception:
                            pass

                    # 3) link rel
                    if not image_url:
                        try:
                            link = prod_page.locator('link[rel="image_src"]')
                            if link.count() > 0:
                                v = link.nth(0).get_attribute('href')
                                if v:
                                    image_url = v
                        except Exception:
                            pass

                    # 4) fallback to img selectors
                    if not image_url:
                        for isel in ['.p-image__image', '[data-testid="product-image"] img', '.product-image img', 'img[itemprop="image"]', '.carousel img', 'img[src*="cdn"], img[src*="trendyol"]', 'img']:
                            try:
                                el = prod_page.locator(isel)
                                if el.count() > 0:
                                    src = el.nth(0).get_attribute('src') or el.nth(0).get_attribute('data-src') or el.nth(0).get_attribute('data-lazy') or ''
                                    if src and src.startswith('//'):
                                        src = 'https:' + src
                                    if src:
                                        image_url = src
                                        break
                            except Exception:
                                continue
                except Exception:
                    image_url = None

                # breadcrumb (3rd level)
                try:
                    crumbs = prod_page.locator('nav[aria-label="breadcrumb"] a')
                    if crumbs.count() >= 3:
                        third = crumbs.nth(2).inner_text().strip()
                    else:
                        crumbs2 = prod_page.locator('.breadcrumb a, .breadcrumbs a, .br .crumb a')
                        if crumbs2.count() >= 3:
                            third = crumbs2.nth(2).inner_text().strip()

                    if not third:
                        try:
                            ld = prod_page.locator('script[type="application/ld+json"]')
                            for i in range(min(ld.count(), 6)):
                                try:
                                    txt = ld.nth(i).inner_text()
                                    import json as _json
                                    doc = _json.loads(txt)
                                    if isinstance(doc, dict) and doc.get('@type', '').lower() == 'breadcrumblist':
                                        items = doc.get('itemListElement', [])
                                        if len(items) >= 3:
                                            third = items[2].get('name')
                                            break
                                except Exception:
                                    continue
                        except Exception:
                            pass
                except Exception:
                    third = None

                # price: prefer non-struck current price
                price = None
                try:
                    # common Trendyol price selectors
                    locs = ['.prc-slg', '[data-testid="price-current"]', '.price', '.prc']
                    for sel in locs:
                        els = prod_page.locator(sel)
                        for j in range(els.count()):
                            txt = els.nth(j).inner_text().strip()
                            # ignore crossed out values that often contain 'TL' but are old prices
                            if 'TL' in txt and not '₺' in txt:
                                # heuristics: if element has <del> child, skip
                                try:
                                    has_del = prod_page.locator(f'{sel} del').count() > 0
                                    if has_del:
                                        continue
                                except Exception:
                                    pass
                                pval = _extract_price_from_text(txt)
                                if pval:
                                    price = pval
                                    break
                        if price:
                            break
                except Exception:
                    price = None

                # material / fabric: search page text for keywords
                material = None
                try:
                    m = re.search(r'(Malzeme|Materyal|Kumaş(?:ı)?|İçerik)[:\s\n]*([A-Za-zÇĞİÖŞÜçğıöşü0-9,\s%-]+)', body, re.I)
                    if m:
                        material = m.group(2).strip()
                    else:
                        # fallback: look in özellikler table
                        t = prod_page.locator('.product-attribute, .product-attributes')
                        if t.count() > 0:
                            material = t.nth(0).inner_text().strip()[:240]
                except Exception:
                    material = None

                out.append({
                    'product_url': h,
                    'product_name': title,
                    'image_url': image_url,
                    'rank': idx,
                    'price': price,
                    'material': material,
                    'category_3': third,
                })
                prod_page.close()
            except Exception as e:
                print('product error', h, e)
                continue

        browser.close()

    # write file
    slug = re.sub(r'[^0-9a-zA-Z]+', '_', category_url)
    out_path = Path(out_dir) / f'trendyol_{slug}_top_sellers.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Wrote', out_path, 'items=', len(out))
    return out_path


if __name__ == '__main__':
    # example usage: update with a real category URL
    sample = 'https://www.trendyol.com/kadin'
    scrape_category(sample, out_dir='data', max_products=80)
