import json, os, re, sys, urllib.request, urllib.parse

OUT = r"d:\Claude\Projects\Trotuarka59\_old"
B = "https://xn--59-6kca3cwancocl.xn--p1ai"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


def save(rel, data):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def q(path):
    return B + urllib.parse.quote(path)


products = json.load(open(os.path.join(OUT, "api_admin_getProducts.json"), encoding="utf-8"))
meta = {}

# 1. product pages
for p in products:
    s = p["slug"]
    try:
        st, html = get(f"{B}/catalog/{s}")
        save(f"products/{s}.html", html)
        t = html.decode("utf-8", "replace")
        title = re.search(r"<title>(.*?)</title>", t)
        desc = re.search(r'<meta name="description" content="([^"]*)"', t)
        h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", t)
        meta[s] = {"status": st, "title": title and title.group(1), "desc": desc and desc.group(1), "h1": h1}
    except Exception as e:
        meta[s] = {"error": str(e)}
json.dump(meta, open(os.path.join(OUT, "products_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("products done", sum(1 for v in meta.values() if v.get("status") == 200))

# 2. verification / metrika tags in all pages
for fn in os.listdir(OUT):
    if fn.endswith(".html"):
        t = open(os.path.join(OUT, fn), encoding="utf-8", errors="replace").read()
        for m in re.findall(r"(yandex-verification[^>]{0,80}|google-site-verification[^>]{0,80}|mc\.yandex[^\"']{0,60}|ym\(\d+)", t):
            print("TAG", fn, m)
for p in ["/catalog/kaliforniya"]:
    pass

# 3. page chunks for gallery/contacts/home/delivery/product
chunks = set()
for fn in os.listdir(OUT):
    if fn.endswith(".html"):
        t = open(os.path.join(OUT, fn), encoding="utf-8", errors="replace").read()
        chunks.update(re.findall(r"/_next/static/chunks/[^\"'\\ ]+\.js", t))
t = open(os.path.join(OUT, "products", "kaliforniya.html"), encoding="utf-8", errors="replace").read()
chunks.update(re.findall(r"/_next/static/chunks/[^\"'\\ ]+\.js", t))
apis = set()
for c in sorted(chunks):
    try:
        st, js = get(B + c)
        save("chunks/" + c.split("/")[-1], js)
        s = js.decode("utf-8", "replace")
        for m in re.findall(r"[\"'`](/api/[^\"'`]+)[\"'`]", s):
            apis.add(m)
    except Exception as e:
        print("chunk err", c, e)
print("APIS", sorted(apis))
for a in sorted(apis):
    if "admin" in a and "getProducts" not in a:
        continue  # do not touch admin endpoints other than public product list
    try:
        st, data = get(B + a)
        save("api" + a.replace("/", "_") + ".json", data)
        print("api", a, st, len(data))
    except Exception as e:
        print("api err", a, e)

# 4. images
imgs = set()
for p in products:
    for arr in p["images"]["originals"]:
        imgs.update(arr)
for fn in os.listdir(OUT):
    if fn.endswith((".html", ".json")):
        t = open(os.path.join(OUT, fn), encoding="utf-8", errors="replace").read()
        imgs.update(re.findall(r"/(?:img|upload)/[^\"'\\)]+?\.(?:jpe?g|png|webp)", t))
        imgs.update(re.findall(r"/_next/static/media/[^\"'\\)]+?\.(?:png|jpe?g|svg|webp)", t))
ok = 0
for i in sorted(imgs):
    try:
        st, data = get(q(i))
        save("assets" + re.sub(r"\s*/\s*", "/", i.strip()), data)
        ok += 1
    except Exception as e:
        print("img err", i, e)
print("images", ok, "of", len(imgs))
