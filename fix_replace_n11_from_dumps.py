import os, json, glob, re
ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, 'proje_analiz_top40.json')
DUMPS = os.path.join(ROOT, 'xhr_dumps')

# load existing out (if missing, create empty skeleton)
if os.path.exists(OUT):
    with open(OUT, 'r', encoding='utf-8') as f:
        out = json.load(f)
else:
    out = []

# collect n11 products from dumps
n11_items = []
if os.path.isdir(DUMPS):
    dumps = sorted(glob.glob(os.path.join(DUMPS, 'n11_*')), key=os.path.getmtime, reverse=True)
    for d in dumps:
        try:
            with open(d, 'r', encoding='utf-8') as fh:
                txt = fh.read()
        except Exception:
            continue
        # robustly extract a JSON array assigned to productListingItems
        def extract_product_array(text):
            key = 'productListingItems'
            idx = text.find(key)
            if idx == -1:
                return []
            arr_start = text.find('[', idx)
            if arr_start == -1:
                return []
            s = text
            depth = 0
            in_str = False
            esc = False
            for idx2 in range(arr_start, len(s)):
                ch = s[idx2]
                if ch == '\\' and in_str:
                    esc = not esc
                    continue
                if ch == '"' and not esc:
                    in_str = not in_str
                else:
                    esc = False
                if not in_str:
                    if ch == '[':
                        depth += 1
                    elif ch == ']':
                        depth -= 1
                        if depth == 0:
                            arr_text = s[arr_start:idx2+1]
                            try:
                                return json.loads(arr_text)
                            except Exception:
                                return []
            return []

        prods_local = extract_product_array(txt)
        for pitem in prods_local:
            title = pitem.get('title') or pitem.get('name') or pitem.get('brand') or ''
            img = None
            imgs = pitem.get('imagePathList') or pitem.get('imagePath') or []
            if isinstance(imgs, list) and len(imgs) > 0:
                img = imgs[0].replace('{0}', '')
            url_part = pitem.get('urlWithoutSellerShop') or pitem.get('url') or ''
            url = 'https://www.n11.com' + url_part if url_part.startswith('/') else url_part
            price = pitem.get('advantageDeliveryPrice') or pitem.get('firstMinFinalPriceForFourteenDay') or None
            try:
                if price is not None:
                    price = float(price)
            except Exception:
                price = None
            item = {'site':'n11','product_name': title, 'price': price, 'image_url': img, 'url': url}
            if item not in n11_items:
                n11_items.append(item)
        if len(n11_items) >= 12:
            break

# fallback: if no dumps found, leave n11_items empty

# replace n11 entries in out
if n11_items:
    # remove existing n11 entries
    others = [i for i in out if i.get('site')!='n11']
    # take first 10 n11_items
    take = n11_items[:10]
    combined = []
    # rebuild out preserving original order of sites (trendyol, amazon, hepsiburada, n11)
    sites = ['trendyol','amazon','hepsiburada','n11']
    for s in sites:
        if s == 'n11':
            combined.extend(take)
        else:
            group = [i for i in others if i.get('site')==s]
            combined.extend(group[:10])
    # if combined less than 40, append others
    if len(combined) < 40:
        for i in others:
            if i not in combined:
                combined.append(i)
            if len(combined) >= 40:
                break
    combined = combined[:40]
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print('Rewrote', OUT, 'with', len(combined), 'items (n11 replaced from dumps)')
else:
    print('No n11 items found in dumps; no change made to', OUT)
