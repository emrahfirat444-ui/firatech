from playwright.sync_api import sync_playwright
import requests, time, json, pathlib, random
OUT = pathlib.Path('xhr_dumps')
OUT.mkdir(exist_ok=True)

# Candidate URLs and API-like endpoints to probe
hep_urls = [
    'https://www.hepsiburada.com/arama?q=telefon',
    'https://www.hepsiburada.com/arama?q=telefon&sayfa=1',
    'https://www.hepsiburada.com/arama?q=telefon&sayfa=2',
    'https://www.hepsiburada.com/ara?q=telefon',
]

n11_urls = [
    'https://www.n11.com/arama?q=telefon',
    'https://www.n11.com/arama?q=telefon&pg=1',
    'https://www.n11.com/arama?q=telefon&pg=2'
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

extra_headers = {
    'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.google.com/',
}


def try_requests(urls, prefix):
    results = []
    for u in urls:
        try:
            hdrs = headers.copy()
            hdrs.update(extra_headers)
            r = requests.get(u, headers=hdrs, timeout=15)
            fname = OUT / f"{prefix}_requests_{int(time.time()*1000)}_{random.randint(0,9999)}.html"
            fname.write_text(r.text, encoding='utf-8')
            results.append({'url':u,'status':r.status_code,'len':len(r.text),'file':str(fname)})
        except Exception as e:
            results.append({'url':u,'error':str(e)})
    return results


def try_playwright(urls, prefix):
    captures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=headers['User-Agent'], locale='tr-TR', viewport={'width':1280,'height':800})
        page = context.new_page()
        def on_response(resp):
            try:
                ct = resp.headers.get('content-type','')
                if 'application/json' in ct or 'search' in resp.url.lower() or 'product' in resp.url.lower():
                    try:
                        j = resp.json()
                        fname = OUT / f"{prefix}_pw_{int(time.time()*1000)}_{random.randint(0,9999)}.json"
                        fname.write_text(json.dumps({'url':resp.url,'json':j}, ensure_ascii=False), encoding='utf-8')
                        captures.append({'url':resp.url,'file':str(fname)})
                    except Exception:
                        pass
            except Exception:
                pass
        page.on('response', on_response)
        for u in urls:
            try:
                page.goto(u, timeout=45000)
                # accept cookies if present
                for sel in ["button:has-text('Kabul')","button:has-text('TAMAM')","button:has-text('Accept')"]:
                    try:
                        el = page.query_selector(sel)
                        if el: el.click()
                    except Exception:
                        pass
                # long scroll
                for _ in range(10):
                    page.evaluate('window.scrollBy(0, document.body.scrollHeight/10)')
                    time.sleep(0.8)
                page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                pass
        try:
            context.close()
            browser.close()
        except Exception:
            pass
    return captures

if __name__ == '__main__':
    print('Request probing Hepsiburada...')
    r1 = try_requests(hep_urls, 'hepsiburada')
    print(r1)
    print('Playwright probing Hepsiburada...')
    p1 = try_playwright(hep_urls, 'hepsiburada')
    print('Captured:', p1)

    print('Request probing N11...')
    r2 = try_requests(n11_urls, 'n11')
    print(r2)
    print('Playwright probing N11...')
    p2 = try_playwright(n11_urls, 'n11')
    print('Captured:', p2)
