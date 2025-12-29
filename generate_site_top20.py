import json
from pathlib import Path
from collections import OrderedDict
import re


REPO = Path('.')
PROJE = REPO / 'proje_analiz_top40.json'
TRENDYOL_IN = REPO / 'trendyol_top10.json'
N11_IN = REPO / 'n11_top10.json'


def normalize_name(s: str) -> str:
    if not s:
        return ''
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^0-9a-zçğıöşüÇĞİÖŞÜ \-]", "", s)
    return s


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return []


def take_top20(site_name: str, site_file, proj_items):
    out = OrderedDict()
    # first add existing site_file items
    for it in site_file:
        name = it.get('product_name') or it.get('name') or it.get('product_name') or ''
        norm = normalize_name(name) or normalize_name(it.get('url',''))
        if not norm:
            continue
        if norm not in out:
            out[norm] = it
        if len(out) >= 20:
            break

    # then supplement from proje_analiz_top40.json where site matches or url contains site
    for it in proj_items:
        if it.get('site','').lower() != site_name and site_name not in (it.get('url','') or ''):
            # also check url contains domain fragment
            url = it.get('url','') or ''
            if site_name not in url:
                continue
        name = it.get('product_name') or it.get('name') or ''
        norm = normalize_name(name) or normalize_name(it.get('url',''))
        if not norm:
            continue
        if norm not in out:
            # when supplementing, try to produce a simpler dict
            out[norm] = {
                'product_name': name,
                'price': it.get('price'),
                'image_url': it.get('image_url') or it.get('image'),
                'url': it.get('url')
            }
        if len(out) >= 20:
            break

    return list(out.values())


def main():
    proj = load_json(PROJE) if PROJE.exists() else []
    trendyol = load_json(TRENDYOL_IN) if TRENDYOL_IN.exists() else []
    n11 = load_json(N11_IN) if N11_IN.exists() else []

    t20 = take_top20('trendyol', trendyol, proj)
    n20 = take_top20('n11', n11, proj)

    (REPO / 'trendyol_top20.json').write_text(json.dumps(t20, ensure_ascii=False, indent=2), encoding='utf-8')
    (REPO / 'n11_top20.json').write_text(json.dumps(n20, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'Wrote trendyol_top20.json ({len(t20)}) and n11_top20.json ({len(n20)})')

if __name__ == '__main__':
    main()
