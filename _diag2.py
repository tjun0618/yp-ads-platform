import urllib.request, urllib.error
try:
    req = urllib.request.Request('http://localhost:5055/')
    with urllib.request.urlopen(req, timeout=5) as r:
        print(f"OK {r.status}")
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8','replace')
    print(f"HTTP {e.code}")
    print(body[:2000])
except Exception as ex:
    print(f"ERR: {ex}")
