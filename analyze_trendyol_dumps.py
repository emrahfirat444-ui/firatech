import json, pathlib, re
from collections import OrderedDict

D = pathlib.Path('xhr_dumps')
files = sorted([p for p in D.glob('trendyol_*.json')])

def walk_json(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk_json(v)
    elif isinstance(o, list):
        for it in o:
            yield from walk_json(it)


def find_price(o):
    # try common keys and patterns
    if not isinstance(o, dict):
        return None
    for k in o.keys():
        if 'price' in k.lower() or 'fiyat' in k.lower() or 'unitPrice' in k or 'sale' in k.lower():
            try:
                txt = str(o.get(k))
                m = re.search(r"[0-9][0-9.,]{0,}", txt)
                if m:
                    return float(m.group(0).replace(',',''))
            except Exception:
                pass
    # search deeper
    for v in o.values():
        if isinstance(v, (dict, list)):
            p = find_price(v)
            if p is not None:
                return p
    return None


def find_image(o):
    if not isinstance(o, dict):
        return None
    for k in o.keys():
        if 'image' in k.lower() or 'img' in k.lower() or 'thumbnail' in k.lower():
            val = o.get(k)
            if isinstance(val, str) and val.startswith('http'):
                return val
            if isinstance(val, list) and len(val)>0 and isinstance(val[0], str):
                return val[0]
    # deeper
    for v in o.values():
        if isinstance(v, (dict, list)):
            im = find_image(v)
            if im:
                return im
    return None


def find_name(o):
    if not isinstance(o, dict):
        return None
    for k in o.keys():
        if k.lower() in ('name','title','productName','product_name','displayName'):
            val = o.get(k)
            if isinstance(val, str) and len(val.strip())>0:
                return val.strip()
    for v in o.values():
        if isinstance(v, (dict, list)):
            nm = find_name(v)
            if nm:
                return nm
    return None


def find_url(o):
    if not isinstance(o, dict):
        return None
    for k in o.keys():
        if 'url' in k.lower() or 'link' in k.lower() or 'slug' in k.lower():
            val = o.get(k)
            if isinstance(val, str) and val:
                return val
    # sometimes urls are in arrays
    for v in o.values():
        if isinstance(v, (dict, list)):
            u = find_url(v)
            if u:
                return u
    return None

products = OrderedDict()

for f in files:
    try:
        j = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        continue
    # if wrapper
    wrapper = j.get('json') if isinstance(j, dict) and 'json' in j else j
    for node in walk_json(wrapper):
        # heuristic: nodes that have name/title or product code
        name = find_name(node)
        if not name:
            continue
        price = find_price(node)
        image = find_image(node)
        url = find_url(node)
        key = name.lower()
        if key not in products:
            products[key] = {'product_name': name, 'price': price, 'image_url': image or '', 'url': url or ''}
        else:
            # fill missing fields
            if products[key].get('price') is None and price is not None:
                products[key]['price'] = price
            if not products[key].get('image_url') and image:
                products[key]['image_url'] = image
            if not products[key].get('url') and url:
                products[key]['url'] = url

# prepare sorted list: prefer items with price, sort descending
items = list(products.values())
with_price = [i for i in items if i.get('price') is not None]
without = [i for i in items if i.get('price') is None]
with_price.sort(key=lambda x: x['price'], reverse=True)
final = with_price + without

# write top10
outf = pathlib.Path('trendyol_top10.json')
outf.write_text(json.dumps(final[:10], ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote', outf, 'items_count=', len(final))

# print sample
import pprint
pprint.pprint(final[:10])
