import requests
url='https://www.n11.com/arama?q=yatak&vueSearch=1'
headers={'User-Agent':'Mozilla/5.0'}
r=requests.get(url, headers=headers, timeout=15)
print('status', r.status_code)
try:
    j=r.json()
    print('top keys:', list(j.keys())[:20])
    data=j.get('data', {})
    print('has productListingItems:', 'productListingItems' in data)
    pls=data.get('productListingItems')
    if pls:
        print('count', len(pls))
        print('sample keys', list(pls[0].keys())[:20])
        print('sample title', pls[0].get('title'))
    else:
        print('no productListingItems in data')
except Exception as e:
    print('json error', e)
    print(r.text[:1000])
