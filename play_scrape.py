from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json, time
sites=[
    {"name":"Trendyol","url":"https://www.trendyol.com/cok-satanlar"},
    {"name":"Hepsiburada","url":"https://www.hepsiburada.com/cok-satanlar"},
    {"name":"N11","url":"https://www.n11.com/cok-satanlar"}
]

keywords_responses = ['search','arama','product','products','listing','suggest','category','getProducts']

results = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for site in sites:
        print(f"=== {site['name']} ===")
        page = browser.new_page()
        collected = []
        responses = []
        def handle_response(resp):
            try:
                url = resp.url
                low = url.lower()
                if any(k in low for k in keywords_responses) or ('api' in low and 'product' in low):
                    try:
                        ct = resp.headers.get('content-type','')
                        if 'application/json' in ct:
                            data = resp.json()
                            responses.append({'url':url,'json':data})
                    except Exception:
                        pass
            except Exception:
                pass
        page.on('response', handle_response)
        try:
            page.goto(site['url'], timeout=30000)
            # try accept cookie buttons
            for sel in ["button:has-text('Kabul')","button:has-text('KABUL')","button:has-text('Kabul Et')","button:has-text('Accept')","button[class*='cookie']","button[id*='cookie']","button[aria-label*='cookie']"]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        el.click(timeout=2000)
                        time.sleep(0.5)
                except Exception:
                    pass
            # scroll to load
            for _ in range(6):
                page.evaluate('window.scrollBy(0, document.body.scrollHeight)')
                time.sleep(1.0)
            page.wait_for_load_state('networkidle', timeout=10000)
            html = page.content()
            soup = BeautifulSoup(html,'html.parser')
            # candidate selectors
            sels = ['.p-card','.p-card__content','.product-card','.product-item','.productListContent-item','.prd','.product','li.search-item','.catalog-list .product','.product-grid .product-item','.column .product']
            cards = []
            for s in sels:
                cards = soup.select(s)
                if cards:
                    break
            # fallback to article or anchor with data-product
            if not cards:
                cards = soup.select('a[href*="/p/"]')[:100]
            # extract
            seen = set()
            for i,card in enumerate(cards[:60]):
                try:
                    title = None
                    for tsel in ['.prd-name','.p-card__title','.product-title','.product-name','h3','h4','a','img']:
                        t = card.select_one(tsel) if hasattr(card,'select_one') else None
                        if t and t.get_text(strip=True):
                            title = t.get_text(strip=True)
                            break
                    if not title:
                        title = card.get('title') if card.get('title') else (card.get('alt') if card.get('alt') else card.get_text(strip=True)[:80])
                    if not title:
                        continue
                    if title in seen:
                        continue
                    seen.add(title)
                    img = ''
                    img_tag = card.select_one('img') if hasattr(card,'select_one') else None
                    if img_tag:
                        img = img_tag.get('data-src') or img_tag.get('src') or ''
                        if img.startswith('//'):
                            img = 'https:'+img
                    link = ''
                    a = card.select_one('a') if hasattr(card,'select_one') else None
                    if a and a.get('href'):
                        link = a.get('href')
                        if link.startswith('/'):
                            parts = site['url'].split('/')
                            link = parts[0]+'//'+parts[2]+link
                    collected.append({'title':title,'img':img,'link':link})
                except Exception:
                    continue
            # also inspect captured JSON responses for product lists
            json_products = []
            for r in responses:
                try:
                    j = r['json']
                    def walk(obj):
                        found = []
                        if isinstance(obj, dict):
                            for k,v in obj.items():
                                if isinstance(v,list):
                                    for item in v:
                                        if isinstance(item,dict) and (any(x in item.keys() for x in ['title','name','productName','product_name']) or any('price' in kk.lower() for kk in item.keys())):
                                            found.append(item)
                                else:
                                    found.extend(walk(v))
                        elif isinstance(obj, list):
                            for it in obj:
                                found.extend(walk(it))
                        return found
                    found = walk(j)
                    for it in found[:50]:
                        json_products.append(it)
                except Exception:
                    continue
            results[site['name']] = {'collected_count':len(collected),'sample':collected[:8],'json_hits': len(json_products)}
            print(json.dumps(results[site['name']], ensure_ascii=False, indent=2))
        except Exception as e:
            print('ERROR', site['name'], str(e))
        finally:
            try:
                page.close()
            except Exception:
                pass
    try:
        browser.close()
    except Exception:
        pass
print('DONE')
