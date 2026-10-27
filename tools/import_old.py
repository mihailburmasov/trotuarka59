"""Разовый импорт со старого сайта в data/ и static/.

Запуск: python -I tools/import_old.py <папка _old>
Читает выгрузку API и картинки старого сайта, пишет:
  data/products.json, data/gallery.json  — источник правды для сборки
  static/img/...                          — фото в WebP (несколько ширин)
  static/img/logo.svg                     — логотип со старого сайта
  static/fonts/*.woff2                    — Oswald + PT Sans (self-hosted)
"""
import json, os, re, sys, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ROOT), "_old")
STATIC = os.path.join(ROOT, "static")
DATA = os.path.join(ROOT, "data")

from PIL import Image  # noqa: E402

CAT = {"TP": "tp", "FP": "fp", "B": "b"}


def webp(src, dst_base, widths, quality=78):
    """src -> dst_base-<w>.webp для каждой ширины; возвращает (w, h) исходника."""
    im = Image.open(src).convert("RGB")
    W, H = im.size
    os.makedirs(os.path.dirname(dst_base), exist_ok=True)
    for w in widths:
        out = f"{dst_base}-{w}.webp"
        if os.path.exists(out):
            continue
        k = min(1.0, w / W)
        im.resize((round(W * k), round(H * k)), Image.LANCZOS).save(out, "WEBP", quality=quality, method=6)
    return W, H


def old_path(p):
    return os.path.join(OLD, "assets", *re.sub(r"\s*/\s*", "/", p.strip()).strip("/").split("/"))


def norm_size(s):
    s = s.replace("x", "х").replace("X", "х")
    return re.sub(r"\s*,\s*", ", ", s).strip()


def per_m2(raw):
    """'11шт. в м2' -> (11, '11 шт.'); сложные случаи — только текст."""
    t = raw.strip()
    m = re.fullmatch(r"(\d+)\s*шт\.?\s*в\s*м2", t)
    if m:
        return int(m.group(1)), f"{m.group(1)} шт."
    m = re.fullmatch(r"(\d+)\s*\+\s*(\d+)\s*шт\.?\s*в\s*м2", t)
    if m:
        return None, f"{m.group(1)} + {m.group(2)} шт. (большая + малая)"
    m = re.fullmatch(r"([\d\s,]+)шт\.?\s*в\s*м2", t)
    if m:
        nums = [n for n in re.split(r"[\s,]+", m.group(1)) if n]
        return None, " / ".join(nums) + " шт. (по размерам)"
    return None, None


def main():
    src = json.load(open(os.path.join(OLD, "api_admin_getProducts.json"), encoding="utf-8"))
    products = []
    for p in src:
        cat = CAT[p["type"]]
        name = p["name"].strip()
        size = norm_size(p["size"])
        n, per_text = per_m2(p["pallet"]) if cat != "b" else (None, None)
        dims = [int(x) for x in re.findall(r"\d+", size.split(",")[0])]
        imgs = []
        for i, arr in enumerate(p["images"]["originals"], 1):
            base = os.path.join(STATIC, "img", "products", p["slug"], str(i))
            W, H = webp(old_path(arr[0]), base, [480, 960, 1600])
            imgs.append({"src": f"/img/products/{p['slug']}/{i}", "w": W, "h": H})
        item = {
            "id": p["id"],
            "slug": p["slug"],
            "name": name,
            "category": cat,
            "size": size,
            "unit": "pcs" if cat == "b" else "m2",
            "price": int(p["price"].strip()),
            "priceColor": int(p["priceColor"].strip()),
            "perM2": n,
            "perM2Text": per_text,
            "colors": [k for k, v in p["colors"].items() if v],
            "images": imgs,
        }
        if cat == "b":
            # бордюр/желоб считаются по длине (длина изделия — первый размер), козырёк — поштучно
            item["calc"] = "qty" if "озыр" in name else "length"
            item["lengthMm"] = dims[0] if dims else None
        else:
            item["calc"] = "area"
        products.append(item)
    json.dump(products, open(os.path.join(DATA, "products.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("products", len(products))

    albums = json.load(open(os.path.join(OLD, "api_api_admin_gallery_getAlbums.json"), encoding="utf-8"))
    slug_by_name = {p["name"].lower(): p["slug"] for p in products}
    gal = []
    for a in albums:
        prod = slug_by_name.get(a["name"].lower())
        folder = prod or "kamen-lomanyj"
        al = {"name": a["name"], "product": prod, "images": []}
        for i, path in enumerate(a["images"], 1):
            base = os.path.join(STATIC, "img", "gallery", folder, str(i))
            W, H = webp(old_path(path), base, [480, 960, 1600])
            al["images"].append({"src": f"/img/gallery/{folder}/{i}", "w": W, "h": H})
        gal.append(al)
    json.dump(gal, open(os.path.join(DATA, "gallery.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("albums", len(gal))

    # прочие фото
    for rel, dst, widths in [
        ("upload/hero/3.jpg", "site/sklad", [960, 1600]),
        ("img/about/1.jpeg", "site/about", [960, 1600]),
        ("img/documents/1.jpg", "docs/1", [480, 1200]),
        ("img/documents/2.jpg", "docs/2", [480, 1200]),
        ("img/documents/3.jpg", "docs/3", [480, 1200]),
    ]:
        W, H = webp(os.path.join(OLD, "assets", *rel.split("/")), os.path.join(STATIC, "img", *dst.split("/")), widths)
        print("img", dst, W, H)

    # логотип: inline SVG из шапки старого сайта
    html = open(os.path.join(OLD, "index.html"), encoding="utf-8").read()
    m = re.search(r'<svg class="Logo_Icon[^"]*"(.*?)</svg>', html, re.S)
    svg = ("<svg" + m.group(1) + "</svg>").replace('fill="#fff"', 'fill="currentColor"', 1)
    open(os.path.join(STATIC, "img", "logo.svg"), "w", encoding="utf-8").write(svg)
    print("logo", len(svg))

    # шрифты (fontsource, кириллица + латиница)
    os.makedirs(os.path.join(STATIC, "fonts"), exist_ok=True)
    for fam, weights in {"oswald": ["500", "600"], "pt-sans": ["400", "700"]}.items():
        for w in weights:
            for sub in ["cyrillic", "latin"]:
                fn = f"{fam}-{sub}-{w}-normal.woff2"
                out = os.path.join(STATIC, "fonts", fn)
                if os.path.exists(out):
                    continue
                url = f"https://cdn.jsdelivr.net/npm/@fontsource/{fam}@5.1.0/files/{fn}"
                with urllib.request.urlopen(url, timeout=30) as r:
                    open(out, "wb").write(r.read())
                print("font", fn)

    # тексты старого сайта — для сверки
    for page in ["delivery", "about"]:
        t = open(os.path.join(OLD, page + ".html"), encoding="utf-8").read()
        chunks = re.findall(r"[А-ЯЁ][^\"\\<>]{60,3000}", t)
        open(os.path.join(ROOT, "tools", f"old_{page}.txt"), "w", encoding="utf-8").write("\n\n".join(dict.fromkeys(chunks)))


if __name__ == "__main__":
    main()
