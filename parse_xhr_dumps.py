import pathlib, json, re
from collections import defaultdict
import os

DUMP = pathlib.Path('xhr_dumps')

def extract_products_from_json(obj):
    found = []
    def walk(o):
        if isinstance(o, dict):
            keys = set(o.keys())
            # heuristic: dicts that contain name/title and price/image/url-like keys
            if (any(k.lower() in ('name','title','productname','product_name') for k in keys)
                or any('product' in k.lower() for k in keys)):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for it in o:
                walk(it)
    walk(obj)
    return found


def normalize_product(d):
    name = d.get('productName') or d.get('name') or d.get('title') or d.get('product_name') or ''
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
    img = d.get('image') or d.get('imageUrl') or d.get('img') or d.get('thumbnail') or ''
    url = d.get('url') or d.get('link') or d.get('productUrl') or ''
    return {'name': name.strip() if name else '', 'price': price, 'image': img, 'url': url}

site_products = defaultdict(list)

for f in DUMP.glob('*.json'):
    name = f.name.lower()
    try:
        content = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        continue
    # content may be {'url':..., 'json':...} or raw json
    j = content.get('json') if isinstance(content, dict) and 'json' in content else content
    # guess site
    if 'trendyol' in name or 'trendyol' in str(j):
        site = 'trendyol'
    elif 'hepsiburada' in name or 'hepsiburada' in str(j):
        site = 'hepsiburada'
    elif 'n11' in name or 'n11' in str(j):
        site = 'n11'
    else:
        # try url
        url = content.get('url') if isinstance(content, dict) else ''
        if isinstance(url, str) and 'hepsiburada' in url:
            site = 'hepsiburada'
        elif isinstance(url, str) and 'n11' in url:
            site = 'n11'
        elif isinstance(url, str) and 'trendyol' in url:
            site = 'trendyol'
        else:
            site = 'other'
    # extract
    prods = extract_products_from_json(j)
    for p in prods:
        norm = normalize_product(p)
        if norm['name']:
            site_products[site].append(norm)

# dedupe and write files
for site, items in site_products.items():
    seen = set()
    out = []
    for it in items:
        n = it['name']
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(it)
    outf = DUMP / f"{site}_products_parsed.json"
    outf.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Wrote', outf, 'items=', len(out))
