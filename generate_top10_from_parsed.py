import pathlib, json
D = pathlib.Path('xhr_dumps')
for site in ['hepsiburada','n11','trendyol']:
    f = D / f"{site}_products_parsed.json"
    if not f.exists():
        continue
    items = json.loads(f.read_text(encoding='utf-8'))
    # sort by price desc where available
    with_price = [i for i in items if i.get('price')]
    without = [i for i in items if not i.get('price')]
    with_price.sort(key=lambda x: x.get('price') or 0, reverse=True)
    final = with_price + without
    topf = pathlib.Path(f"{site}_top10.json")
    topf.write_text(json.dumps(final[:10], ensure_ascii=False, indent=2), encoding='utf-8')
    print('Wrote', topf)
