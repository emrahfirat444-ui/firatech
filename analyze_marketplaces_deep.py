from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json, time, re, pathlib, os, random

OUTDIR = pathlib.Path('xhr_dumps')
OUTDIR.mkdir(exist_ok=True)

sites = [
    {"name":"Trendyol","urls":[
        "https://www.trendyol.com/cok-satanlar",
        "https://www.trendyol.com/sr?st=cok+satanlar",
        "https://www.trendyol.com/sr?q=yeni+ürünler",
        "https://www.trendyol.com/sr?q=telefon"
    ]},
    {"name":"Hepsiburada","urls":[
        "https://www.hepsiburada.com/cok-satanlar",
        "https://www.hepsiburada.com/arama?q=telefon",
        "https://www.hepsiburada.com/kategori/telefon"
    ]},
    {"name":"N11","urls":[
        "https://www.n11.com/cok-satanlar",
        "https://www.n11.com/arama?q=telefon",
        "https://www.n11.com/arama?q=yeni"
    ]}
]

KEYWORDS = ['product','products','search','listing','popular','best','items','hits','suggest','catalog','search','searchResults','results']


def extract_products_from_json(obj):
    found = []
    def walk(o):
        if isinstance(o, dict):
            keys = set(o.keys())
            if (('name' in keys or 'title' in keys or 'productName' in keys or 'product_name' in keys)
                and any(k.lower().find('price')!=-1 for k in keys) or ('image' in keys and ('name' in keys or 'title' in keys))):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for it in o:
                walk(it)
    walk(obj)
    return found


def normalize_product(d):
    name = d.get('productName') or d.get('name') or d.get('title') or d.get('product_name') or d.get('title_tr') or ''
    price = None
    for k in d.keys():
        if 'price' in k.lower() or 'fiyat' in k.lower() or 'amount' in k.lower():
            try:
                txt = str(d.get(k))
                m = re.search(r"[0-9][0-9.,]{0,}", txt)
                if m:
                    price = float(m.group(0).replace(',',''))
                    break
            except Exception:
                pass
    img = d.get('image') or d.get('imageUrl') or d.get('image_url') or d.get('thumbnail') or d.get('img') or ''
    url = d.get('url') or d.get('productUrl') or d.get('detailUrl') or d.get('link') or ''
    return {'name': name.strip(), 'price': price, 'image': img, 'url': url}


def find_price_in_obj(o):
    if isinstance(o, dict):
        for k,v in o.items():
            lk = k.lower()
            if 'price' in lk or 'fiyat' in lk or 'amount' in lk or 'sale' in lk:
                try:
                    txt = str(v)
                    m = re.search(r"[0-9][0-9.,]{0,}", txt)
                    if m:
                        return float(m.group(0).replace(',',''))
                except Exception:
                    pass
        for v in o.values():
            res = find_price_in_obj(v)
            if res is not None:
                return res
    elif isinstance(o, list):
        for it in o:
            res = find_price_in_obj(it)
            if res is not None:
                return res
    return None


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    overall = {}
    for site in sites:
        site_results = {'json_count':0,'extracted':[],'saved_json_files':[]}
        page = browser.new_page()
        collected = []

        def on_response(resp):
            try:
                url = resp.url
                low = url.lower()
                ct = resp.headers.get('content-type','')
                if 'application/json' in ct or any(k in low for k in KEYWORDS) or 'api' in low or 'search' in low:
                    try:
                        j = resp.json()
                        timestamp = int(time.time()*1000)
                        fname = OUTDIR / f"{site['name'].lower()}_{timestamp}_{random.randint(0,9999)}.json"
                        try:
                            fname.write_text(json.dumps({'url':url,'json':j}, ensure_ascii=False))
                            site_results['saved_json_files'].append(str(fname))
                        except Exception:
                            pass
                        collected.append({'url':url,'json':j})
                    except Exception:
                        pass
            except Exception:
                pass

        page.on('response', on_response)

        try:
            for url in site.get('urls',[]):
                try:
                    page.goto(url, timeout=45000)
                except Exception:
                    pass
                # try accept cookies
                for sel in ["button:has-text('Kabul')","button:has-text('KABUL')","button:has-text('Tümünü kabul et')","button:has-text('Tümünü kabul')","button:has-text('Accept')","button:has-text('TAMAM')"]:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            el.click(timeout=2000)
                            time.sleep(0.3)
                    except Exception:
                        pass
                # human-like interactions
                try:
                    for _ in range(6):
                        x = random.randint(100, 800)
                        y = random.randint(100, 600)
                        try:
                            page.mouse.move(x, y)
                        except Exception:
                            pass
                        page.evaluate('window.scrollBy(0, document.body.scrollHeight/3)')
                        time.sleep(random.uniform(0.6,1.2))
                    page.wait_for_load_state('networkidle', timeout=10000)
                except Exception:
                    pass

            site_results['json_count'] = len(collected)

            # parse collected
            found = []
            for item in collected:
                try:
                    prods = extract_products_from_json(item['json'])
                    for p in prods:
                        norm = normalize_product(p)
                        if norm['price'] is None:
                            price = find_price_in_obj(p)
                            if price is not None:
                                norm['price'] = price
                        if norm['name']:
                            found.append(norm)
                except Exception:
                    pass

            # dedupe and sort
            seen = set()
            out = []
            for it in found:
                n = it['name']
                if not n or n in seen:
                    continue
                seen.add(n)
                out.append(it)
            out_with_price = [i for i in out if i.get('price') is not None]
            out_no_price = [i for i in out if i.get('price') is None]
            out_with_price.sort(key=lambda x: x['price'] if x.get('price') else 0, reverse=True)
            final = out_with_price + out_no_price

            site_results['extracted'] = final
            overall[site['name']] = {
                'json_count': site_results['json_count'],
                'products_extracted': len(final),
                'sample': final[:10]
            }

            # write outputs per site
            try:
                outf = OUTDIR / f"{site['name'].lower()}_products.json"
                outf.write_text(json.dumps({'meta':{'json_count':site_results['json_count']}, 'products': final}, ensure_ascii=False, indent=2))
            except Exception:
                pass

            # if Trendyol, write top10
            if site['name'].lower().find('trendyol')!=-1:
                try:
                    topf = pathlib.Path('trendyol_top10.json')
                    topf.write_text(json.dumps(final[:10], ensure_ascii=False, indent=2))
                    print('Trendyol top10 written to', topf)
                except Exception as e:
                    print('could not write trendyol top10', e)

            print(site['name'], 'json_count=', site_results['json_count'], 'products=', len(final))
        except Exception as e:
            print('error', site['name'], e)
        finally:
            try:
                page.close()
            except Exception:
                pass

    try:
        browser.close()
    except Exception:
        pass

print('Overall summary:')
print(json.dumps(overall, ensure_ascii=False, indent=2))
