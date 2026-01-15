from playwright.sync_api import sync_playwright
import json,os,sqlite3,time

data_path = os.path.join('data','trendyol_https_www_trendyol_com_kadin_top_sellers.json')
out_json = os.path.join('data','trendyol_https_www_trendyol_com_kadin_top_sellers_with_cat.json')
db_path = os.path.join('db','trendyol_products.db')

os.makedirs('db', exist_ok=True)

with open(data_path,'r',encoding='utf-8') as f:
    data = json.load(f)

conn = sqlite3.connect(db_path)
c = conn.cursor()
# create table
c.execute('''CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rank INTEGER,
    product_url TEXT UNIQUE,
    product_name TEXT,
    price TEXT,
    material TEXT,
    image_url TEXT,
    category_1 TEXT,
    category_2 TEXT,
    category_3 TEXT,
    raw_json TEXT
)
''')
conn.commit()

filled = 0
visited = 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    for rec in data:
        visited += 1
        url = rec.get('product_url')
        if not url:
            continue
        # Skip if category_3 already present
        if rec.get('category_3'):
            # still insert into DB
            pass
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state('networkidle', timeout=60000)
        except Exception:
            try:
                time.sleep(1)
                page.goto(url, timeout=60000)
                page.wait_for_load_state('networkidle', timeout=60000)
            except Exception:
                continue
        # Try JSON-LD breadcrumbs first
        crumbs = []
        try:
            scripts = page.query_selector_all('script[type="application/ld+json"]')
            for s in scripts:
                try:
                    txt = s.inner_text()
                    if not txt or len(txt.strip())<10:
                        continue
                    j = json.loads(txt)
                except Exception:
                    continue
                # If it's a list, iterate
                arr = j if isinstance(j,list) else [j]
                for obj in arr:
                    if not isinstance(obj,dict):
                        continue
                    t = obj.get('@type') or obj.get('type')
                    if t and ('BreadcrumbList' in t or 'Breadcrumb' in t):
                        ile = obj.get('itemListElement') or obj.get('breadcrumb') or []
                        if isinstance(ile,dict):
                            ile = [ile]
                        for item in ile:
                            # item may be {'name':..} or {'item':{'name':..}}
                            name = None
                            if isinstance(item,dict):
                                if 'name' in item:
                                    name = item.get('name')
                                elif 'item' in item and isinstance(item['item'],dict):
                                    name = item['item'].get('name')
                                elif 'position' in item and isinstance(item.get('item'),dict):
                                    name = item['item'].get('name')
                            if name:
                                crumbs.append(name.strip())
        except Exception:
            pass
        # If no crumbs from JSON-LD, try DOM selectors
        if not crumbs:
            try:
                sel_variants = [
                    'nav[aria-label="breadcrumb"] a',
                    'nav[aria-label="breadcrumb"] span',
                    'ul.breadcrumb li a',
                    'ol.breadcrumb li a',
                    'div[class*="breadcrumb"] a',
                    'div[class*="breadcrumb"] span',
                    'a[class*="breadcrumb"]',
                    'div.breadcrumbs a',
                    'div.breadcrumbs li a',
                    'header .breadcrumb a'
                ]
                for sel in sel_variants:
                    els = page.query_selector_all(sel)
                    if not els:
                        continue
                    for e in els:
                        try:
                            t = e.inner_text().strip()
                            if t:
                                crumbs.append(t)
                        except Exception:
                            continue
                    if crumbs:
                        break
            except Exception:
                pass
        # Normalize crumbs list: remove empty, dedup consecutive
        norm = []
        prev = None
        for cval in crumbs:
            if not cval:
                continue
            cv = cval.strip()
            if cv==prev:
                continue
            norm.append(cv)
            prev = cv
        crumbs = norm
        # set category_1/2/3
        cat1 = crumbs[0] if len(crumbs)>=1 else None
        cat2 = crumbs[1] if len(crumbs)>=2 else None
        cat3 = crumbs[2] if len(crumbs)>=3 else None
        if cat3 and not rec.get('category_3'):
            rec['category_3'] = cat3
            filled += 1
        # prepare image_url string
        img = rec.get('image_url')
        img_str = None
        if isinstance(img,dict):
            if isinstance(img.get('contentUrl'), list) and img.get('contentUrl'):
                img_str = img.get('contentUrl')[0]
            elif img.get('contentUrl'):
                img_str = img.get('contentUrl')
            elif img.get('url'):
                img_str = img.get('url')
            else:
                img_str = json.dumps(img,ensure_ascii=False)
        else:
            img_str = img
        # Insert or replace into DB
        try:
            raw = json.dumps(rec, ensure_ascii=False)
            c.execute('''INSERT OR REPLACE INTO products (rank,product_url,product_name,price,material,image_url,category_1,category_2,category_3,raw_json)
                         VALUES (?,?,?,?,?,?,?,?,?,?)''',(
                rec.get('rank'), rec.get('product_url'), rec.get('product_name'), rec.get('price'), rec.get('material'), img_str, cat1, cat2, cat3, raw
            ))
            conn.commit()
        except Exception:
            conn.rollback()
        # polite delay
        time.sleep(0.5)
    browser.close()

# write updated JSON
with open(out_json,'w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)

print(f'Visited={visited} updated_category3={filled} db={db_path} out_json={out_json}')
conn.close()

http://localhost:8501
