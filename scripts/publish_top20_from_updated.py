import json,os
in_path = os.path.join('data','trendyol_https_www_trendyol_com_kadin_top_sellers_with_cat.json')
out_path = 'trendyol_top20.json'

def first_image_str(img):
    if isinstance(img,dict):
        if isinstance(img.get('contentUrl'), list) and img.get('contentUrl'):
            return img.get('contentUrl')[0]
        if img.get('contentUrl'):
            return img.get('contentUrl')
        if img.get('url'):
            return img.get('url')
        return json.dumps(img, ensure_ascii=False)
    return img

if not os.path.exists(in_path):
    print('input not found:', in_path)
    raise SystemExit(1)

with open(in_path,'r',encoding='utf-8') as f:
    data = json.load(f)

out = []
for rec in data[:20]:
    out.append({
        'rank': rec.get('rank'),
        'product_url': rec.get('product_url'),
        'product_name': rec.get('product_name'),
        'price': rec.get('price'),
        'material': rec.get('material'),
        'image_url': first_image_str(rec.get('image_url')),
        'category_1': rec.get('category_1'),
        'category_2': rec.get('category_2'),
        'category_3': rec.get('category_3')
    })

with open(out_path,'w',encoding='utf-8') as f:
    json.dump(out,f,ensure_ascii=False,indent=2)

print('Wrote', out_path, 'items=', len(out))
