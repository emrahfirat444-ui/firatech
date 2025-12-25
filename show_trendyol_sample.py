import json, pathlib, re
p = pathlib.Path('trendyol_top10.json')
if not p.exists():
    print('file not found')
else:
    raw = json.loads(p.read_text(encoding='utf-8'))
    if isinstance(raw, dict) and 'products' in raw:
        items = raw['products']
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    def normalize(it):
        d = dict(it)
        if 'product_name' not in d and 'name' in d:
            d['product_name'] = d.get('name')
        if 'image_url' not in d and 'image' in d:
            d['image_url'] = d.get('image')
        p = d.get('price')
        if p is not None and not isinstance(p,(int,float)):
            m = re.search(r"[0-9][0-9.,]{0,}", str(p))
            if m:
                d['price'] = float(m.group(0).replace(',',''))
            else:
                d['price'] = None
        return d
    norm = [normalize(i) for i in items][:10]
    import pprint
    pprint.pprint(norm)
