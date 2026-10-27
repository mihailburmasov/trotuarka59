import json, os, re, urllib.request, urllib.parse

OUT = r"d:\Claude\Projects\Trotuarka59\_old"
B = "https://xn--59-6kca3cwancocl.xn--p1ai"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def save(rel, data):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "wb").write(data)


imgs = set()
for a in ["/api/admin/gallery/getAlbums", "/api/admin/hero/getHero"]:
    d = get(B + a)
    save("api" + a.replace("/", "_") + ".json", d)
    t = d.decode("utf-8")
    print(a, t[:1500])
    imgs.update(re.findall(r"/(?:img|upload)/[^\"\\]+?\.(?:jpe?g|png|webp)", t))
ok = 0
for i in sorted(imgs):
    try:
        save("assets" + re.sub(r"\s*/\s*", "/", i.strip()), get(B + urllib.parse.quote(i)))
        ok += 1
    except Exception as e:
        print("err", i, e)
print("images", ok, len(imgs))

# competitors
for name, url in [("iris", "https://fabrika-iris.com/"), ("astek", "https://www.stroi-perm.ru/catalog/k-107985-plitka_trotuarnaya")]:
    try:
        save(f"competitors/{name}.html", get(url))
        print("comp ok", name)
    except Exception as e:
        print("comp err", name, e)
