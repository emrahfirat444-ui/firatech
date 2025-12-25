import requests
import json
import time
import os
from urllib.parse import urlencode

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, 'trendyol_top10.json')

# Default categories to try (mattress example seen earlier: 27)
CATEGORY_IDS = [27, 1, 1663, 1016]

BASE = 'https://apigw.trendyol.com/discovery-sfint-browsing-service/api/top-rankings/top-ranking-contents'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'application/json, text/plain, */*'
}

collected = []
seen_keys = set()


def walk_json(o, source_url=None):
    results = []
    if isinstance(o, dict):
        # detect product-like
        if any(k in o for k in ['productId','id']) and any(k in o for k in ['images','image','imageUrl']):
            name = o.get('title') or o.get('name') or o.get('displayName') or ''
            # image
            image = ''
            for k in ['images','image','imageUrl','thumbnail']:
                if k in o:
                    v = o[k]
                    if isinstance(v, list) and v:
                        # may be dicts or strings
                        if isinstance(v[0], str):
                            image = v[0]
                        elif isinstance(v[0], dict):
                            # try url/key
                            for key in ['url','original','imageUrl']:
                                if key in v[0]:
                                    image = v[0][key]
                                    break
                    elif isinstance(v, str):
                        image = v
                    if image:
                        break
            # price
            price = None
            for k in ['price','listPrice','salePrice','salePriceText','priceText']:
                if k in o:
                    try:
                        price = float(str(o[k]).replace('.', '').replace(',', '.'))
                        break
                    except:
                        pass
            # url
            url = o.get('url') or o.get('productLink') or ''
            results.append({'product_name': name or '', 'price': price, 'image_url': image or '', 'url': url or source_url or ''})
        for v in o.values():
            results.extend(walk_json(v, source_url))
    elif isinstance(o, list):
        for it in o:
            results.extend(walk_json(it, source_url))
    return results


def fetch_for_category(cat_id, page=1, page_size=20):
    params = dict(rankingType='bestSeller', webGenderId=1, page=page, pageSize=page_size,
                  categoryId=cat_id, channelId=1, storefrontId=1, language='tr', countryCode='TR')
    url = BASE + '?' + urlencode(params)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print('Non-200', r.status_code, 'for', url)
            return []
        j = r.json()
        return walk_json(j, source_url=url)
    except Exception as e:
        print('Error fetching', url, e)
        return []


def main():
    for cid in CATEGORY_IDS:
        print('Querying category', cid)
        items = fetch_for_category(cid)
        time.sleep(0.5)
        for it in items:
            key = (it.get('product_name') or '')[:200] + '|' + (it.get('url') or '')[:300]
            if not key.strip():
                continue
            if key in seen_keys:
                continue
            seen_keys.add(key)
            collected.append(it)
    # if no items found, fall back to existing trending file
    if not collected:
        print('No ranking items collected — falling back to existing file if present')
        if os.path.exists(OUT):
            with open(OUT, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            print('Using existing', len(existing))
            return
        else:
            print('No existing file to fallback to')
            return

    # prefer items with image+price, but keep others
    def score(it):
        s = 0
        if it.get('image_url'):
            s += 3
        if it.get('price'):
            s += 2
        return s
    collected.sort(key=score, reverse=True)

    final = collected[:20]
    # dedupe by name
    out = []
    names = set()
    for it in final:
        n = (it.get('product_name') or '').strip()
        if not n or n in names:
            continue
        names.add(n)
        out.append(it)
        if len(out) >= 10:
            break

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('Wrote', OUT, 'items_count=', len(out))

if __name__ == '__main__':
    main()
