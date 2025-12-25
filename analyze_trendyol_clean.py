import json
import re
import glob
import os

IMAGE_RE = re.compile(r"https?://[\w\.-]*/[\w\.-]+\.(?:jpg|jpeg|png|webp)", re.I)
PRICE_RE = re.compile(r"\d[\d\.,]*")

NAME_KEYS = {"name","title","productName","displayName","product_name","productTitle","label","titleText"}
PRICE_KEYS = {"price","originalPrice","salePrice","discountedPrice","listPrice","currentPrice","priceValue","priceText"}
IMAGE_KEYS = {"image","imageUrl","images","image_url","thumbnail","thumbnailUrl"}
ID_KEYS = {"id","productId","sku","product_id"}


def iter_json(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_json(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_json(item)


def find_strings(obj):
    res = []
    if isinstance(obj, str):
        res.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            res.extend(find_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            res.extend(find_strings(v))
    return res


def is_image_url(s):
    if not isinstance(s, str):
        return False
    return bool(IMAGE_RE.search(s))


def find_image(obj):
    # search direct keys
    if isinstance(obj, dict):
        for k in IMAGE_KEYS:
            if k in obj:
                v = obj[k]
                if isinstance(v, str) and is_image_url(v):
                    return v
                if isinstance(v, list) and v:
                    for it in v:
                        if isinstance(it, str) and is_image_url(it):
                            return it
                        if isinstance(it, dict):
                            for vv in it.values():
                                if isinstance(vv, str) and is_image_url(vv):
                                    return vv
    # fallback: find any string that looks like image
    for s in find_strings(obj):
        if is_image_url(s):
            return s
    return None


def find_price(obj):
    # direct price keys
    if isinstance(obj, dict):
        for k in PRICE_KEYS:
            if k in obj:
                v = obj[k]
                if isinstance(v, (int, float)) and v > 0:
                    return float(v)
                if isinstance(v, str):
                    m = PRICE_RE.search(v)
                    if m:
                        return float(m.group(0).replace('.', '').replace(',', '.'))
    # fallback: scan strings
    for s in find_strings(obj):
        if isinstance(s, str):
            m = PRICE_RE.search(s)
            if m and len(m.group(0)) >= 2:
                try:
                    return float(m.group(0).replace('.', '').replace(',', '.'))
                except:
                    pass
    # numeric fields
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
    return None


def find_name(obj):
    if isinstance(obj, dict):
        for k in NAME_KEYS:
            if k in obj and isinstance(obj[k], str) and len(obj[k]) > 3:
                return obj[k].strip()
    # fallback: any long string that looks like a title
    for s in find_strings(obj):
        if isinstance(s, str) and len(s) > 10 and not s.lower().startswith('<'):
            # avoid html fragments
            return s.strip()
    return None


def find_url(obj):
    for s in find_strings(obj):
        if isinstance(s, str) and 'trendyol.com' in s:
            return s
        if isinstance(s, str) and '/p/' in s and len(s) < 400:
            return s
    return None


def looks_like_product(d):
    name = find_name(d)
    price = find_price(d)
    img = find_image(d)
    pid = None
    if isinstance(d, dict):
        for k in ID_KEYS:
            if k in d:
                pid = d[k]
                break
    # require name and at least one of price/image/id/url
    if not name:
        return False
    url = find_url(d)
    if price or img or pid or url:
        return True
    return False


def score_product(d):
    s = 0
    if find_price(d) is not None:
        s += 3
    if find_image(d):
        s += 3
    if find_url(d):
        s += 1
    if any(k in d for k in ID_KEYS if isinstance(d, dict)):
        s += 1
    name = find_name(d)
    if name:
        s += min(3, len(name) // 10)
    return s


def normalize(d):
    return {
        'product_name': find_name(d) or '',
        'price': find_price(d),
        'image_url': find_image(d) or '',
        'url': find_url(d) or '',
        'score': score_product(d)
    }


def main():
    root = os.path.dirname(__file__)
    dumps = glob.glob(os.path.join(root, 'xhr_dumps', 'trendyol*.json'))
    candidates = []
    seen = set()
    for p in dumps:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                j = json.load(f)
        except Exception as e:
            # skip non-json
            continue
        for node in iter_json(j):
            if not isinstance(node, dict):
                continue
            if looks_like_product(node):
                norm = normalize(node)
                key = (norm['product_name'] or '')[:100] + '|' + (norm['url'] or '')[:200]
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((norm['score'], norm))
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = [c[1] for c in candidates[:30]]
    # dedupe further by name
    final = []
    names = set()
    for it in top:
        n = (it['product_name'] or '').strip()
        if not n:
            continue
        if n in names:
            continue
        names.add(n)
        final.append(it)
        if len(final) >= 10:
            break
    out_path = os.path.join(root, 'trendyol_top10.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print('Wrote', out_path, 'items_count=', len(final))


if __name__ == '__main__':
    main()
