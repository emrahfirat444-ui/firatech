import json
import csv
import re
from pathlib import Path
from collections import defaultdict, Counter
from statistics import median


FILES = [
    "proje_analiz_top40.json",
    "trendyol_top10.json",
    "hepsiburada_top10.json",
    "n11_top10.json",
]


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def extract_field(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return None


NAME_KEYS = ["title", "name", "product_name", "ad", "urun_adi", "baslik"]
PRICE_KEYS = ["price", "fiyat", "price_text", "price_display", "price_str"]
CAT_KEYS = ["category", "kategori", "cat", "kategory"]
URL_KEYS = ["url", "link", "href", "product_url"]


def normalize_name(s: str) -> str:
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^0-9a-zçğıöşüÇĞİÖŞÜ \-]", "", s)
    s = s.strip()
    return s


def extract_numeric_price(s: str):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s)
    s = s.replace(".", "").replace(" ", "")
    m = re.search(r"(\d+)", s)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def main():
    repo = Path(".")
    agg = {}
    counts = Counter()

    for fp in FILES:
        p = repo / fp
        if not p.exists():
            continue
        data = load_json(p)
        if not data:
            continue
        # data may be list or dict with items
        items = data if isinstance(data, list) else data.get("items") if isinstance(data, dict) else None
        if items is None:
            # try to treat top-level dict values as list
            if isinstance(data, dict):
                items = [data]
            else:
                continue

        for it in items:
            name = extract_field(it, NAME_KEYS) or extract_field(it, ["product","title_tr"])
            url = extract_field(it, URL_KEYS)
            price = extract_field(it, PRICE_KEYS)
            cat = extract_field(it, CAT_KEYS)

            norm = normalize_name(name if name else str(url or ""))
            if not norm:
                continue

            entry = agg.setdefault(norm, {
                "orig_names": Counter(),
                "count": 0,
                "categories": Counter(),
                "prices": [],
                "price_texts": Counter(),
                "urls": Counter(),
                "sources": Counter(),
            })

            entry["count"] += 1
            if name:
                entry["orig_names"][name] += 1
            if cat:
                entry["categories"][cat] += 1
            if price is not None:
                num = extract_numeric_price(price)
                if num is not None:
                    entry["prices"].append(num)
                entry["price_texts"][str(price)] += 1
            if url:
                entry["urls"][str(url)] += 1
            entry["sources"][fp] += 1

    results = []
    for norm, v in agg.items():
        most_common_name = v["orig_names"].most_common(1)
        name = most_common_name[0][0] if most_common_name else norm
        categories = [c for c, _ in v["categories"].most_common()]
        urls = [u for u, _ in v["urls"].most_common(5)]
        sources = [s for s, _ in v["sources"].most_common()]

        price_repr = None
        if v["prices"]:
            try:
                price_repr = int(median(v["prices"]))
            except Exception:
                price_repr = v["prices"][0]
        elif v["price_texts"]:
            price_repr = v["price_texts"].most_common(1)[0][0]

        results.append({
            "name": name,
            "normalized_name": norm,
            "count": v["count"],
            "categories": categories,
            "price": price_repr,
            "sample_urls": urls,
            "sources": sources,
        })

    results.sort(key=lambda x: (-x["count"], x["name"]))

    out_json = repo / "most_frequent_products.json"
    out_csv = repo / "most_frequent_products.csv"

    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "count", "categories", "price", "sample_urls", "sources"])
        for r in results:
            writer.writerow([
                r["name"],
                r["count"],
                " | ".join(r.get("categories", [])),
                r.get("price", ""),
                " | ".join(r.get("sample_urls", [])),
                " | ".join(r.get("sources", [])),
            ])

    print(f"Wrote {out_json} ({len(results)} items) and {out_csv}")
    # print top 10 summary
    for i, r in enumerate(results[:20], 1):
        print(f"{i}. {r['name']} — count={r['count']} price={r.get('price')} sources={','.join(r.get('sources',[]))}")


if __name__ == "__main__":
    main()
