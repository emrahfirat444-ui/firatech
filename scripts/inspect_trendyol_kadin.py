import json,sys
p='data/trendyol_https_www_trendyol_com_kadin_top_sellers.json'
try:
    with open(p,'r',encoding='utf-8') as f:
        data=json.load(f)
except Exception as e:
    print('ERROR loading',p,e)
    sys.exit(1)
for i,rec in enumerate(data[:20],1):
    img=rec.get('image_url')
    img0=None
    if isinstance(img,dict):
        if isinstance(img.get('contentUrl'), list) and img.get('contentUrl'):
            img0=img.get('contentUrl')[0]
        elif img.get('contentUrl'):
            img0=img.get('contentUrl')
        elif img.get('url'):
            img0=img.get('url')
        else:
            img0=str(img)[:140]
    else:
        img0=img
    print(f"{i}. rank={rec.get('rank')}\n   url={rec.get('product_url')}\n   image={img0}\n   category_3={rec.get('category_3')}\n")
