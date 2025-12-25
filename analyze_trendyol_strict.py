import json
import re
import glob
import os

IMAGE_RE = re.compile(r"https?://[\w\.-]*/[\w\.-]+\.(?:jpg|jpeg|png|webp)", re.I)
PRICE_RE = re.compile(r"\d[\d\.,]*")
BAD_SUBSTR = ["cookielaw.org", "otPc", "otFlat", "otPcCenter", "consent", "vendorlist", "datalayer", "apigw.trendyol.com/discovery-mweb-accountgw-service", "googleData.json"]
IMAGE_HOSTS = ["cdn.dsmcdn.com", "cdn.trendyol.com", "productimages.trendyol.com", "trendyol-res.cloudinary.com", "cdn.dsmcdn.com.tr", "trendyol.com"]

NAME_KEYS = {"name","title","productName","displayName","product_name","productTitle","label","titleText","title"}
PRICE_KEYS = {"price","originalPrice","salePrice","discountedPrice","listPrice","currentPrice","priceValue","priceText","amount"}
IMAGE_KEYS = {"image","imageUrl","images","image_url","thumbnail","thumbnailUrl","img","picture"}
ID_KEYS = {"id","productId","sku","product_id","pid","product_id"}


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


def contains_bad(node):
    for s in find_strings(node):
        if not isinstance(s, str):
            continue
        low = s.lower()
        for b in BAD_SUBSTR:
            if b.lower() in low:
                return True
    return False


def is_image_url(s):
    if not isinstance(s, str):
        return False
    if not IMAGE_RE.search(s):
        return False
    low = s.lower()
    for host in IMAGE_HOSTS:
        if host in low:
            return True
    return False


def find_image(node):
    if isinstance(node, dict):
        for k in IMAGE_KEYS:
            if k in node:
                v = node[k]
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
    for s in find_strings(node):
        if is_image_url(s):
            return s
    return None


def find_price(node):
    if isinstance(node, dict):
        for k in PRICE_KEYS:
            if k in node:
                v = node[k]
                if isinstance(v, (int, float)) and 1 <= v <= 1000000:
                    return float(v)
                if isinstance(v, str):
                    m = PRICE_RE.search(v)
                    if m:
                        raw = m.group(0)
                        try:
                            val = float(raw.replace('.', '').replace(',', '.'))
                            if 1 <= val <= 1000000:
                                return val
                        except:
                            pass
    for s in find_strings(node):
        if not isinstance(s, str):
            continue
        m = PRICE_RE.search(s)
        if m:
            raw = m.group(0)
            try:
                val = float(raw.replace('.', '').replace(',', '.'))
                if 1 <= val <= 1000000:
                    return val
            except:
                pass
    if isinstance(node, dict):
        for v in node.values():
            if isinstance(v, (int, float)) and 1 <= v <= 1000000:
                return float(v)
    return None


def find_name(node):
    if isinstance(node, dict):
        for k in NAME_KEYS:
            if k in node and isinstance(node[k], str) and len(node[k].strip()) > 3:
                return node[k].strip()
    for s in find_strings(node):
        if isinstance(s, str) and len(s) > 8 and 'http' not in s and not s.strip().isdigit():
            return s.strip()
    return None


def find_url(node):
    for s in find_strings(node):
        if isinstance(s, str) and 'trendyol.com' in s:
            return s
        if isinstance(s, str) and '/p/' in s and len(s) < 500:
            return s
    return None


def node_is_product(node):
    if contains_bad(node):
        return False
    name = find_name(node)
    image = find_image(node)
    price = find_price(node)
    url = find_url(node)
    pid = None
    if isinstance(node, dict):
        for k in ID_KEYS:
            if k in node:
                pid = node[k]
                break
    # strict: must have name and image and price (or url+price)
    if not name:
        return False
    if image and price and (price >= 1):
        return True
    if url and price and (price >= 1):
        return True
    return False


def score(node):
    s = 0
    if find_price(node):
        s += 3
    if find_image(node):
        s += 3
    if find_url(node):
        s += 2
    if find_name(node):
        s += 1
    return s


def normalize(node):
    return {
        'product_name': find_name(node) or '',
        'price': find_price(node),
        'image_url': find_image(node) or '',
        'url': find_url(node) or '',
        'score': score(node)
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
        except Exception:
            continue
        for node in iter_json(j):
            if not isinstance(node, dict):
                continue
            if node_is_product(node):
                norm = normalize(node)
                key = (norm['product_name'] or '')[:150] + '|' + (norm['url'] or '')[:300]
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((norm['score'], norm))
    candidates.sort(key=lambda x: x[0], reverse=True)
    final = []
    names = set()
    for sc, it in candidates:
        n = (it['product_name'] or '').strip()
        if not n or n in names:
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
