"""Сборка статического сайта тротуарка59.рф.

    python -I build.py          — стенд: незаполненные факты видны бейджем
    python -I build.py --prod   — прод: падает, пока в данных есть todo
    python -I build.py --base /trotuarka59 --staging
                                — копия для GitHub Pages: пути с префиксом, noindex

Данные: data/company.json (факты), data/products.json (каталог),
data/gallery.json (фото работ), data/content.json (тексты).
Результат: dist/ — статические файлы; адреса без .html,
nginx отдаёт их через try_files $uri $uri.html (см. deploy/nginx.conf).
"""
import hashlib, html, json, os, re, shutil, sys
from datetime import date
from urllib.parse import quote

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
PROD = "--prod" in sys.argv
STAGING = "--staging" in sys.argv
BASE = sys.argv[sys.argv.index("--base") + 1].rstrip("/") if "--base" in sys.argv else ""


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


C = load("company.json")
P = load("products.json")
G = load("gallery.json")
T = load("content.json")
CATS = T["categories"]
COLORS = T["colors"]
SITE = C["siteUrl"]
YEAR = date.today().year
TODOS = []


# ---------- helpers ----------

def esc(s):
    return html.escape(str(s), quote=True)


def is_todo(v):
    return isinstance(v, dict) and "todo" in v


def fact(v):
    """Текст факта; незаполненный — бейдж на стенде."""
    if is_todo(v):
        TODOS.append(v["todo"])
        return f'<span class="todo">{esc(v["todo"])} — нужно от клиента</span>'
    return esc(v)


def money(n):
    return f"{n:,}".replace(",", " ")


def unit(p):
    return "м²" if p["unit"] == "m2" else "шт"


def dims(s):
    return s.replace("х", "×")


def has_color(p):
    return any(c != "grey" for c in p["colors"])


def plural(n, one, few, many):
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


def cat_url(cat):
    return f"/catalog/{CATS[cat]['slug']}"


def p_url(p):
    return f"/catalog/{p['slug']}"


def p_title(p):
    pre = CATS[p["category"]]["prefix"]
    return f"{pre} «{p['name']}»" if pre else p["name"]


def img(src, alt, w, h, sizes, widths=(480, 960, 1600), lazy=True, cls=""):
    srcset = ", ".join(f"{src}-{x}.webp {x}w" for x in widths)
    mid = widths[1] if len(widths) > 1 else widths[0]
    attrs = 'loading="lazy" decoding="async"' if lazy else 'fetchpriority="high" decoding="async"'
    c = f' class="{cls}"' if cls else ""
    return (f'<img{c} src="{src}-{mid}.webp" srcset="{srcset}" sizes="{sizes}" '
            f'width="{w}" height="{h}" alt="{esc(alt)}" {attrs}>')


def icon(name, cls="ic"):
    return f'<svg class="{cls}" aria-hidden="true"><use href="/img/icons.svg#{name}"/></svg>'


# ---------- derived facts (из данных, не руками) ----------

def by_slug(s):
    return next(p for p in P if p["slug"] == s)


TP = [p for p in P if p["category"] == "tp"]
FACTS = {
    "count": len(P),
    "count_text": f"{len(P)} {plural(len(P), 'позиция', 'позиции', 'позиций')}",
    "min_tp": money(min(p["price"] for p in TP)),
    "min_tp_color": money(min(p["priceColor"] for p in TP if has_color(p))),
    "price_300": money(by_slug("kaliforniya")["price"]),
    "price_300_color": money(by_slug("kaliforniya")["priceColor"]),
    "price_bordyur": money(by_slug("bordyur-sadovyj")["price"]),
    "price_zhelob": money(by_slug("zhelob-vodostochnyj")["price"]),
}
MIN_BY_CAT = {c: min(p["price"] for p in P if p["category"] == c) for c in CATS}


def fmt(s):
    return s.format_map(FACTS)


# ---------- JSON-LD ----------

def org_ld():
    d = {
        "@type": "HomeAndConstructionBusiness",
        "@id": SITE + "/#org",
        "name": C["brand"],
        "legalName": C["legalName"],
        "description": C["tagline"],
        "url": SITE + "/",
        "logo": SITE + "/img/og.jpg",
        "image": SITE + "/img/og.jpg",
        "telephone": C["phone"],
        "email": C["email"],
        "address": {"@type": "PostalAddress", "streetAddress": C["address"]["street"],
                    "addressLocality": C["address"]["city"], "addressRegion": C["address"]["region"],
                    "addressCountry": "RU"},
        "openingHours": C["hoursSchema"],
        "areaServed": C["areaServed"],
        "taxID": C["inn"],
        "priceRange": f"{FACTS['min_tp']}–{money(max(p['priceColor'] for p in P))} ₽",
    }
    same = [v for v in C["messengers"].values() if not is_todo(v)]
    if same:
        d["sameAs"] = same
    return d


def crumbs_ld(items):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + (u if u != "/" else "/")}
        for i, (n, u) in enumerate(items)]}


def faq_ld(faq):
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": fmt(q["a"])}} for q in faq]}


def product_ld(p):
    code = "MTK" if p["unit"] == "m2" else "H87"
    offers = [{"@type": "Offer", "priceCurrency": "RUB", "price": p["price"], "name": "Серый",
               "priceSpecification": {"@type": "UnitPriceSpecification", "price": p["price"], "priceCurrency": "RUB",
                                      "unitCode": code, "unitText": unit(p)},
               "seller": {"@id": SITE + "/#org"}, "url": SITE + p_url(p)}]
    if has_color(p):
        offers.append({"@type": "Offer", "priceCurrency": "RUB", "price": p["priceColor"], "name": "Цветной",
                       "priceSpecification": {"@type": "UnitPriceSpecification", "price": p["priceColor"],
                                              "priceCurrency": "RUB", "unitCode": code, "unitText": unit(p)},
                       "seller": {"@id": SITE + "/#org"}, "url": SITE + p_url(p)})
    return {"@type": "Product", "name": p_title(p), "sku": str(p["id"]),
            "description": product_desc(p),
            "image": [SITE + i["src"] + "-960.webp" for i in p["images"]],
            "brand": {"@type": "Brand", "name": C["brand"]},
            "category": CATS[p["category"]]["name"],
            "color": ", ".join(COLORS[c]["name"] for c in p["colors"]),
            "size": dims(p["size"]) + " мм",
            "offers": offers}


def ld_script(*objs):
    data = {"@context": "https://schema.org", "@graph": list(objs)}
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


# ---------- page shell ----------

NAV = [("/catalog", "Каталог"), ("/gallery", "Наши работы"), ("/delivery", "Доставка"),
       ("/about", "О компании"), ("/contacts", "Контакты")]


def asset_v():
    h = hashlib.md5()
    for f in ("css/style.css", "js/main.js"):
        h.update(open(os.path.join(ROOT, "static", f), "rb").read())
    return h.hexdigest()[:8]


V = asset_v()


def messenger_links(cls="msg"):
    m = C["messengers"]
    out = [f'<a class="{cls} {cls}--wa" href="{m["whatsapp"]}" target="_blank" rel="noopener" data-goal="whatsapp">{icon("wa")}<span>WhatsApp</span></a>',
           f'<a class="{cls} {cls}--tg" href="{m["telegram"]}" target="_blank" rel="noopener" data-goal="telegram">{icon("tg")}<span>Telegram</span></a>']
    if is_todo(m["max"]):
        out.append(f'<span class="{cls} {cls}--max is-todo">{icon("max")}<span>MAX</span>{fact(m["max"])}</span>')
    else:
        out.append(f'<a class="{cls} {cls}--max" href="{esc(m["max"])}" target="_blank" rel="noopener" data-goal="max">{icon("max")}<span>MAX</span></a>')
    return "".join(out)


def header(path):
    links = "".join(
        f'<a href="{u}"{" aria-current=page" if path == u or path.startswith(u + "/") else ""}>{n}</a>' for u, n in NAV)
    return f'''<header class="hdr" id="top">
  <div class="wrap hdr__in">
    <a class="logo" href="/" aria-label="{esc(C["brand"])} — на главную">{LOGO}</a>
    <nav class="nav" id="nav" aria-label="Основное меню">{links}</nav>
    <div class="hdr__contact">
      <a class="hdr__phone" href="tel:{C["phone"]}" data-goal="phone">{C["phoneDisplay"]}</a>
      <span class="hdr__hours">{esc(C["hours"])}</span>
    </div>
    <button class="btn btn--accent btn--sm hdr__cta" type="button" data-open-form data-subject="Обратный звонок">Заказать звонок</button>
    <button class="burger" type="button" aria-controls="nav" aria-expanded="false" aria-label="Меню"><span></span></button>
  </div>
</header>'''


def footer():
    nav = "".join(f'<li><a href="{u}">{n}</a></li>' for u, n in NAV)
    cats = "".join(f'<li><a href="{cat_url(c)}">{CATS[c]["name"]}</a></li>' for c in CATS)
    utm = "https://sitomika.ru/?utm_source=client_site&utm_medium=footer&utm_campaign=" + quote(C["siteHost"])
    return f'''<footer class="ftr">
  <div class="wrap ftr__grid">
    <div class="ftr__brand">
      <a class="logo logo--light" href="/" aria-label="{esc(C["brand"])}">{LOGO}</a>
      <p>{esc(C["tagline"])}.</p>
      <div class="ftr__msg">{messenger_links("chip")}</div>
    </div>
    <div><h2 class="ftr__h">Каталог</h2><ul>{cats}</ul></div>
    <div><h2 class="ftr__h">Разделы</h2><ul>{nav}</ul></div>
    <div class="ftr__contacts"><h2 class="ftr__h">Контакты</h2>
      <a class="ftr__phone" href="tel:{C["phone"]}" data-goal="phone">{C["phoneDisplay"]}</a>
      <a href="mailto:{C["email"]}" data-goal="email">{C["email"]}</a>
      <p>{esc(C["address"]["full"])}<br>{esc(C["hours"])}</p>
    </div>
  </div>
  <div class="wrap ftr__bottom">
    <p>© {YEAR} {esc(C["brand"])} · {esc(C["legalName"])}, ИНН {C["inn"]}, ОГРНИП {C["ogrnip"]}</p>
    <p><a href="/politika-konfidentsialnosti">Политика конфиденциальности</a> · Цены на сайте не являются публичной офертой</p>
    <p><a class="studio" href="{utm}" target="_blank" rel="noopener">Разработано в sitomika.ru</a></p>
  </div>
</footer>'''


def form_block(subject="Заявка с сайта", compact=False, fid="f"):
    return f'''<form class="lead{" lead--compact" if compact else ""}" data-lead novalidate>
  <input type="hidden" name="subject" value="{esc(subject)}">
  <div class="lead__hp" aria-hidden="true"><label>Сайт<input name="website" tabindex="-1" autocomplete="off"></label></div>
  <label class="fld"><span>Имя</span><input name="name" autocomplete="name" placeholder="Как к вам обращаться"></label>
  <label class="fld"><span>Телефон *</span><input name="phone" type="tel" inputmode="tel" autocomplete="tel" required placeholder="+7 (___) ___-__-__"></label>
  <label class="fld fld--wide"><span>Что нужно</span><textarea name="comment" rows="3" placeholder="Модель, цвет, площадь или количество, адрес доставки"></textarea></label>
  <label class="consent"><input type="checkbox" name="consent" value="1" checked required>
    <span>Согласен на обработку персональных данных по <a href="/politika-konfidentsialnosti" target="_blank">политике конфиденциальности</a></span></label>
  <button class="btn btn--accent" type="submit">Отправить заявку</button>
  <p class="lead__status" role="status" aria-live="polite"></p>
</form>'''


def modal():
    return f'''<dialog class="modal" id="lead-modal" aria-labelledby="lead-modal-h">
  <button class="modal__x" type="button" data-close aria-label="Закрыть">×</button>
  <p class="eyebrow">Ответим в рабочее время</p>
  <h2 id="lead-modal-h" class="modal__h">Рассчитаем стоимость</h2>
  <p class="modal__lead">Оставьте телефон — перезвоним, уточним количество и цвет, посчитаем доставку. Или позвоните: <a href="tel:{C["phone"]}" data-goal="phone">{C["phoneDisplay"]}</a></p>
  {form_block("Заявка из окна")}
</dialog>
<dialog class="lightbox" id="lightbox" aria-label="Просмотр фото">
  <button class="lightbox__x" type="button" data-close aria-label="Закрыть">×</button>
  <button class="lightbox__nav lightbox__prev" type="button" aria-label="Предыдущее фото">‹</button>
  <img alt="">
  <button class="lightbox__nav lightbox__next" type="button" aria-label="Следующее фото">›</button>
  <p class="lightbox__cap"></p>
</dialog>'''


def mobile_bar():
    return f'''<div class="mbar" aria-label="Быстрая связь">
  <a href="tel:{C["phone"]}" data-goal="phone">{icon("phone")}<span>Позвонить</span></a>
  <a href="{C["messengers"]["whatsapp"]}" target="_blank" rel="noopener" data-goal="whatsapp">{icon("wa")}<span>WhatsApp</span></a>
  <button type="button" data-open-form data-subject="Заявка с мобильной панели">{icon("calc")}<span>Расчёт</span></button>
</div>'''


def cookie_bar():
    return '''<div class="cookie" hidden>
  <p>Сайт использует cookie, чтобы корректно работать и показывать встроенную карту. Подробнее — в <a href="/politika-konfidentsialnosti">политике конфиденциальности</a>.</p>
  <button class="btn btn--sm btn--dark" type="button" data-cookie-ok>Понятно</button>
</div>'''


def metrika():
    if not C.get("metrikaId"):
        return ""
    i = int(C["metrikaId"])
    return f'''<script>(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");ym({i},"init",{{clickmap:true,trackLinks:true,accurateTrackBounce:true,webvisor:true}});window.YM_ID={i};</script><noscript><div><img src="https://mc.yandex.ru/watch/{i}" style="position:absolute;left:-9999px" alt=""></div></noscript>'''


def page(path, title, desc, body, ld=(), og_img="/img/og.jpg", crumbs=None, extra_head=""):
    if len(title) > 70:
        print(f"  ! title {len(title)} симв.: {path}")
    if len(desc) > 165:
        print(f"  ! description {len(desc)} симв.: {path}")
    if body.count("<h1") != 1:
        raise SystemExit(f"H1 на {path}: {body.count('<h1')}")
    url = SITE + (path if path != "/" else "/")
    lds = list(ld)
    if crumbs:
        lds.append(crumbs_ld(crumbs))
    bc = ""
    if crumbs:
        parts = []
        for i, (n, u) in enumerate(crumbs):
            parts.append(f'<span aria-current="page">{esc(n)}</span>' if i == len(crumbs) - 1 else f'<a href="{u}">{esc(n)}</a>')
        bc = f'<nav class="crumbs wrap" aria-label="Хлебные крошки">{"<i>/</i>".join(parts)}</nav>'
    cfg = {"endpoint": C.get("formEndpoint"), "phone": C["phoneDisplay"], "tel": C["phone"]}
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:locale" content="ru_RU">
<meta property="og:site_name" content="{esc(C["brand"])}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{og_img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#23211e">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/img/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/img/apple-touch-icon.png">
<link rel="preload" href="/fonts/oswald-cyrillic-600-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/pt-sans-cyrillic-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/css/style.css?v={V}">
{extra_head}{ld_script(*lds) if lds else ""}
<script>document.documentElement.classList.add("js");window.SITE={json.dumps(cfg, ensure_ascii=False)};</script>
{metrika()}
</head>
<body>
<a class="skip" href="#main">К содержанию</a>
{header(path)}
<main id="main">
{bc}
{body}
</main>
{footer()}
{mobile_bar()}
{modal()}
{cookie_bar()}
<script src="/js/main.js?v={V}" defer></script>
</body>
</html>'''


# ---------- blocks ----------

def swatches(p, big=False):
    s = "".join(f'<i style="--c:{COLORS[c]["hex"]}" title="{COLORS[c]["name"]}"></i>' for c in p["colors"])
    names = ", ".join(COLORS[c]["name"].lower() for c in p["colors"])
    return f'<span class="sw{" sw--big" if big else ""}" role="img" aria-label="Цвета: {names}">{s}</span>'


def price_html(p, big=False):
    u = unit(p)
    col = (f'<span class="price__alt">цветная — <b>{money(p["priceColor"])} ₽</b>/{u}</span>' if has_color(p) else "")
    return (f'<div class="price{" price--big" if big else ""}"><span class="price__main"><b>{money(p["price"])} ₽</b>/{u}'
            f'<small>{"серая" if p["unit"] == "m2" else "серый"}</small></span>{col}</div>')


def card(p, lazy=True):
    i = p["images"][0]
    per = f'<span>{esc(p["perM2Text"])} в м²</span>' if p.get("perM2Text") else ""
    return f'''<article class="card" data-cat="{p["category"]}" data-colors="{" ".join(p["colors"])}" data-price="{p["price"]}">
  <a class="card__img" href="{p_url(p)}" tabindex="-1" aria-hidden="true">{img(i["src"], p_title(p), i["w"], i["h"], "(max-width: 600px) 50vw, 300px", lazy=lazy)}</a>
  <div class="card__body">
    <p class="card__cat">{CATS[p["category"]]["short"]}</p>
    <h3 class="card__name"><a href="{p_url(p)}">{esc(p["name"])}</a></h3>
    <p class="card__meta"><span>{dims(p["size"])} мм</span>{per}</p>
    {swatches(p)}
    {price_html(p)}
  </div>
</article>'''


def calc_data():
    return [{"slug": p["slug"], "name": p_title(p), "cat": p["category"], "calc": p["calc"], "unit": p["unit"],
             "price": p["price"], "priceColor": p["priceColor"] if has_color(p) else None,
             "perM2": p.get("perM2"), "lengthMm": p.get("lengthMm")} for p in P]


def calculator(p=None):
    """Калькулятор: м² → шт → ₽, метры → шт бордюра → ₽. Считает только по ценам из каталога."""
    sel = ""
    if p is None:
        opts = ""
        for c in CATS:
            o = "".join(f'<option value="{x["slug"]}">{esc(x["name"])} — {money(x["price"])} ₽/{unit(x)}</option>'
                        for x in P if x["category"] == c)
            opts += f'<optgroup label="{CATS[c]["name"]}">{o}</optgroup>'
        sel = f'<label class="fld fld--wide"><span>Модель</span><select name="product">{opts}</select></label>'
    slug = f' data-product="{p["slug"]}"' if p else ""
    data = calc_data() if p is None else [x for x in calc_data() if x["slug"] == p["slug"]]
    return f'''<script type="application/json" class="calc-data">{json.dumps(data, ensure_ascii=False)}</script>
<form class="calc" data-calc{slug} onsubmit="return false">
  {sel}
  <div class="calc__row">
    <label class="fld" data-for="area"><span>Площадь, м²</span><input name="area" type="number" min="0" step="0.5" value="20" inputmode="decimal"></label>
    <label class="fld" data-for="area"><span>Запас на подрезку</span><select name="reserve"><option value="0">без запаса</option><option value="5" selected>+5%</option><option value="10">+10%</option></select></label>
    <label class="fld" data-for="length"><span>Длина, пог. м</span><input name="meters" type="number" min="0" step="0.5" value="20" inputmode="decimal"></label>
    <label class="fld" data-for="qty"><span>Количество, шт</span><input name="qty" type="number" min="0" step="1" value="10" inputmode="numeric"></label>
    <fieldset class="fld seg" data-color><legend>Цвет</legend>
      <label><input type="radio" name="color" value="grey" checked><span>Серый</span></label>
      <label><input type="radio" name="color" value="color"><span>Цветной</span></label>
    </fieldset>
  </div>
  <output class="calc__out" aria-live="polite">
    <span class="calc__line" data-out="need"></span>
    <span class="calc__line" data-out="pcs"></span>
    <span class="calc__sum" data-out="sum"></span>
    <span class="calc__note">Без учёта доставки. Точную сумму подтвердит менеджер.</span>
  </output>
  <button class="btn btn--accent" type="button" data-calc-send>Отправить расчёт менеджеру</button>
</form>'''


def faq_html(faq, h="Частые вопросы"):
    items = "".join(f'<details class="faq__i"><summary><h3>{esc(q["q"])}</h3></summary><p>{esc(fmt(q["a"]))}</p></details>' for q in faq)
    return f'<section class="sec faq" id="faq"><div class="wrap wrap--narrow"><h2 class="h2">{h}</h2><div class="faq__list">{items}</div></div></section>'


def cta_band(title="Поможем выбрать и рассчитаем стоимость", text="Оставьте телефон — специалист перезвонит, подскажет модель и посчитает количество с доставкой."):
    return f'''<section class="sec band" id="zayavka">
  <div class="hero__bg" aria-hidden="true"></div>
  <div class="wrap band__in">
    <div class="band__txt reveal">
      <h2 class="h2">{title}</h2>
      <p>{text}</p>
      <p class="band__alt">Или напишите в мессенджер:</p>
      <div class="band__msg">{messenger_links("chip")}</div>
    </div>
    <div class="band__form reveal">{form_block("Заявка: помощь с выбором")}</div>
  </div>
</section>'''


def gallery_strip(n=8):
    items = []
    for a in G:
        for i in a["images"][:3]:
            items.append((a, i))
    # чередуем альбомы, чтобы лента была разнообразной
    picked, seen = [], {}
    for a, i in items:
        seen.setdefault(a["name"], []).append(i)
    while len(picked) < n and any(seen.values()):
        for name in list(seen):
            if seen[name] and len(picked) < n:
                picked.append((name, seen[name].pop(0)))
    out = "".join(
        f'<a class="strip__i" href="{i["src"]}-1600.webp" data-lightbox="strip" data-cap="{esc(nm)}">{img(i["src"], "Укладка плитки «" + nm + "» — наша работа", i["w"], i["h"], "(max-width: 600px) 70vw, 320px", widths=(480, 960))}<span>{esc(nm)}</span></a>'
        for nm, i in picked)
    return f'<div class="strip">{out}</div>'


# ---------- pages ----------

def home():
    pops = ["kaliforniya", "8-kirpichej", "klever-krakovskij", "antik", "volna-zigzag", "rakushka", "bordyur-sadovyj", "zhelob-vodostochnyj"]
    cats = ""
    for c, d in CATS.items():
        cnt = sum(1 for p in P if p["category"] == c)
        src = d["img"]
        cats += f'''<a class="cat reveal" href="{cat_url(c)}">
  <span class="cat__img">{img(src, d["name"], 1080, 1080, "(max-width: 700px) 100vw, 33vw", widths=(480, 960))}</span>
  <span class="cat__body"><span class="cat__name">{d["name"]}</span>
  <span class="cat__meta">{cnt} {plural(cnt, "модель", "модели", "моделей")} · <span class="nw">от {money(MIN_BY_CAT[c])} ₽/{"м²" if c != "b" else "шт"}</span></span>
  <span class="cat__go">Смотреть {icon("arrow")}</span></span></a>'''
    ben = "".join(f'<li class="ben reveal">{icon(b["icon"], "ben__ic")}<h3>{esc(b["title"])}</h3><p>{esc(fmt(b["text"]))}</p></li>' for b in T["benefits"])
    steps = "".join(f'<li class="step reveal"><span class="step__n">{i}</span><h3>{esc(s["title"])}</h3><p>{esc(s["text"])}</p></li>' for i, s in enumerate(T["steps"], 1))
    popular = "".join(card(by_slug(s)) for s in pops)
    hero_img = by_slug("antik")
    g_antik = next(a for a in G if a["product"] == "antik")
    body = f'''<section class="hero">
  <div class="hero__bg" aria-hidden="true"></div>
  <div class="wrap hero__in">
    <div class="hero__txt">
      <p class="eyebrow eyebrow--light">Производство в Краснокамске · доставка по Перми и краю</p>
      <h1 class="h1">Тротуарная плитка и бордюры <span>от производителя</span> в Перми</h1>
      <p class="hero__lead">Плитка для дорожек и дворов, фасадная плитка под камень, бордюры и водосточные желоба. Цены завода, склад готовой продукции, доставка манипулятором.</p>
      <div class="hero__btns">
        <a class="btn btn--accent btn--lg" href="/catalog">Смотреть каталог и цены</a>
        <a class="btn btn--ghost btn--lg" href="#calc">Рассчитать количество</a>
      </div>
      <ul class="hero__facts">
        <li><b>от {FACTS["min_tp"]} ₽</b><span>за м² плитки</span></li>
        <li><b>{FACTS["count"]}</b><span>{plural(FACTS["count"], "модель", "модели", "моделей")} в каталоге</span></li>
        <li><b>{len(COLORS)} {plural(len(COLORS), "цвет", "цвета", "цветов")}</b><span>серый и цветные</span></li>
        <li><b>1 год</b><span>гарантии</span></li>
      </ul>
    </div>
    <div class="hero__pics" aria-hidden="false">
      <figure class="hero__pic hero__pic--a">{img(g_antik["images"][4]["src"], "Дорожка из плитки «Антик» в нескольких цветах — работа наших клиентов", 1080, 1080, "(max-width: 900px) 60vw, 420px", lazy=False, widths=(480, 960))}</figure>
      <figure class="hero__pic hero__pic--b">{img("/img/site/sklad", "Склад готовой продукции и машина с манипулятором в Краснокамске", 1440, 1080, "(max-width: 900px) 50vw, 340px", widths=(960, 1600))}<figcaption>Наш склад в Краснокамске</figcaption></figure>
      <figure class="hero__pic hero__pic--c">{img(hero_img["images"][0]["src"], "Плитка «Антик»", hero_img["images"][0]["w"], hero_img["images"][0]["h"], "200px", widths=(480, 960))}</figure>
    </div>
  </div>
</section>

<section class="sec" id="catalog">
  <div class="wrap">
    <div class="sec__head"><h2 class="h2">Что мы производим</h2><a class="more" href="/catalog">Весь каталог {icon("arrow")}</a></div>
    <div class="cats">{cats}</div>
  </div>
</section>

<section class="sec sec--tint">
  <div class="wrap">
    <div class="sec__head"><h2 class="h2">Популярные модели</h2><a class="more" href="/catalog">Все {FACTS["count_text"]} {icon("arrow")}</a></div>
    <div class="grid">{popular}</div>
    <p class="note">Тротуарная и фасадная плитка — цена за м². Бордюры, желоба и козырьки — цена за штуку.</p>
  </div>
</section>

<section class="sec calc-sec" id="calc">
  <div class="wrap calc-sec__in">
    <div class="calc-sec__txt reveal">
      <p class="eyebrow">Калькулятор</p>
      <h2 class="h2">Сколько нужно плитки и сколько это стоит</h2>
      <p>Выберите модель и укажите площадь — калькулятор пересчитает метры в штуки и покажет сумму по ценам каталога. Для бордюров и желобов укажите длину в метрах — получите количество штук.</p>
    </div>
    <div class="calc-sec__box reveal">{calculator()}</div>
  </div>
</section>

<section class="sec">
  <div class="wrap">
    <h2 class="h2">Почему покупают у нас</h2>
    <ul class="bens">{ben}</ul>
  </div>
</section>

<section class="sec sec--dark">
  <div class="wrap">
    <div class="sec__head"><h2 class="h2">Работы наших клиентов</h2><a class="more more--light" href="/gallery">Все фото {icon("arrow")}</a></div>
  </div>
  {gallery_strip(10)}
</section>

<section class="sec">
  <div class="wrap">
    <h2 class="h2">Как заказать</h2>
    <ol class="steps">{steps}</ol>
  </div>
</section>

{faq_html(T["faq"])}
{cta_band()}'''
    return page("/", "Тротуарная плитка в Перми от производителя — цены | Тротуарка59",
                f"Тротуарная и фасадная плитка, бордюры и желоба от производителя в Краснокамске. Плитка от {FACTS['min_tp']} ₽/м², бордюры поштучно, доставка манипулятором по Перми и краю.",
                body, ld=[org_ld(), faq_ld(T["faq"])], extra_head='')


def filters_bar(active=None):
    chips = f'<a class="chip-f{" is-on" if active is None else ""}" href="/catalog">Все <span>{len(P)}</span></a>'
    for c, d in CATS.items():
        n = sum(1 for p in P if p["category"] == c)
        chips += f'<a class="chip-f{" is-on" if active == c else ""}" href="{cat_url(c)}">{d["short"]} <span>{n}</span></a>'
    colors = "".join(f'<label class="cf"><input type="checkbox" value="{k}"><i style="--c:{v["hex"]}"></i>{v["name"]}</label>' for k, v in COLORS.items())
    return f'''<div class="filters" data-filters>
  <nav class="filters__cats" aria-label="Категории">{chips}</nav>
  <div class="filters__more">
    <fieldset class="filters__colors"><legend>Цвет</legend>{colors}</fieldset>
    <label class="filters__sort"><span>Сортировка</span><select data-sort><option value="">по умолчанию</option><option value="asc">сначала дешевле</option><option value="desc">сначала дороже</option></select></label>
  </div>
  <p class="filters__empty" hidden>Нет моделей с выбранными цветами. <button type="button" data-reset>Сбросить фильтр</button></p>
</div>'''


def catalog_page():
    secs = ""
    for c, d in CATS.items():
        items = "".join(card(p) for p in P if p["category"] == c)
        secs += f'<section class="cat-sec" data-cat-sec="{c}"><div class="sec__head"><h2 class="h2 h2--sm"><a href="{cat_url(c)}">{d["name"]}</a></h2><span class="unit-tag">цена за {"м²" if c != "b" else "штуку"}</span></div><div class="grid">{items}</div></section>'
    body = f'''<section class="page-head"><div class="wrap">
  <h1 class="h1 h1--page">Каталог: тротуарная плитка, фасадная плитка, бордюры</h1>
  <p class="page-head__lead">{FACTS["count_text"]} собственного производства. Плитка продаётся квадратными метрами, бордюры, желоба и козырьки — поштучно. Серые и цветные изделия, цены — на каждой карточке.</p>
</div></section>
<section class="sec sec--top0"><div class="wrap">{filters_bar()}{secs}</div></section>
{cta_band("Не нашли нужную модель?", "Позвоните или оставьте заявку — подскажем по наличию, цветам и количеству.")}'''
    il = {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": SITE + p_url(p), "name": p_title(p)} for i, p in enumerate(P)]}
    return page("/catalog", "Каталог тротуарной плитки и бордюров с ценами | Тротуарка59",
                f"Каталог: {FACTS['count_text']} — тротуарная и фасадная плитка (цена за м²), бордюры, желоба и козырьки (цена за шт). Производство в Краснокамске, доставка по Перми.",
                body, ld=[il], crumbs=[("Главная", "/"), ("Каталог", "/catalog")])


def category_page(c):
    d = CATS[c]
    items = "".join(card(p) for p in P if p["category"] == c)
    # вопросы по теме категории; у фасадной своих нет — блок не выводим
    faq = {"tp": [q for q in T["faq"] if "плит" in q["q"].lower()][:3],
           "b": [q for q in T["faq"] if "Бордюр" in q["q"]], "fp": []}[c]
    path = cat_url(c)
    faq_block = faq_html(faq, "Вопросы о " + ("бордюрах и желобах" if c == "b" else "тротуарной плитке")) if faq else ""
    body = f'''<section class="page-head"><div class="wrap">
  <h1 class="h1 h1--page">{d["name"]} {"в Перми" if c != "b" else "в Перми — цена за штуку"}</h1>
  <p class="page-head__lead">{esc(d["lead"])}</p>
</div></section>
<section class="sec sec--top0"><div class="wrap">{filters_bar(c)}<div class="grid">{items}</div></div></section>
{faq_block}
{cta_band()}'''
    min_u = "₽/шт" if c == "b" else "₽/м²"
    return page(path, f"{d['title']} | Тротуарка59" if len(d["title"]) < 56 else d["title"],
                f"{d['name']}: {sum(1 for p in P if p['category'] == c)} моделей от {money(MIN_BY_CAT[c])} {min_u}. Производство в Краснокамске, склад готовой продукции, доставка манипулятором по Перми и краю.",
                body, ld=[faq_ld(faq)] if faq else [], crumbs=[("Главная", "/"), ("Каталог", "/catalog"), (d["name"], path)])


def product_desc(p):
    u = unit(p)
    col = f", цветная — {money(p['priceColor'])} ₽/{u}" if has_color(p) else ""
    per = f" В 1 м² — {p['perM2Text']}" if p.get("perM2") else ""
    if p["unit"] == "pcs":
        return f"{p_title(p)} {dims(p['size'])} мм — {money(p['price'])} ₽ за штуку{col}. Продаётся поштучно, доставка по Перми и краю."
    return f"{p_title(p)} {dims(p['size'])} мм — {money(p['price'])} ₽/м² серая{col}.{per}. Производство в Краснокамске, доставка по Перми."


def product_page(p):
    c = p["category"]
    imgs = p["images"]
    main = imgs[0]
    thumbs = ""
    if len(imgs) > 1:
        thumbs = '<div class="pg__thumbs">' + "".join(
            f'<button type="button" class="pg__t{" is-on" if k == 0 else ""}" data-src="{i["src"]}" aria-label="Фото {k + 1}">{img(i["src"], "", i["w"], i["h"], "96px", widths=(480,))}</button>'
            for k, i in enumerate(imgs)) + "</div>"
    u = unit(p)
    rows = [("Размер", f"{dims(p['size'])} мм")]
    if p.get("perM2Text"):
        rows.append(("Количество в 1 м²", p["perM2Text"]))
    if p["unit"] == "pcs" and p.get("lengthMm") and p["calc"] == "length":
        n = 1000 / p["lengthMm"]
        rows.append(("На 1 пог. м", f"{n:g} шт"))
    rows.append(("Единица продажи", "квадратный метр (м²)" if p["unit"] == "m2" else "штука"))
    rows.append(("Цвета", ", ".join(COLORS[x]["name"] for x in p["colors"])))
    rows.append(("Цена, серый", f"{money(p['price'])} ₽/{u}"))
    if has_color(p):
        rows.append(("Цена, цветной", f"{money(p['priceColor'])} ₽/{u}"))
    spec = "".join(f"<tr><th>{esc(a)}</th><td>{esc(b)}</td></tr>" for a, b in rows)
    album = next((a for a in G if a["product"] == p["slug"]), None)
    works = ""
    if album:
        works = f'<section class="sec sec--dark"><div class="wrap"><div class="sec__head"><h2 class="h2">«{esc(p["name"])}» в работах клиентов</h2><a class="more more--light" href="/gallery#{p["slug"]}">Все фото {icon("arrow")}</a></div></div><div class="strip">' + "".join(
            f'<a class="strip__i" href="{i["src"]}-1600.webp" data-lightbox="w" data-cap="{esc(p["name"])}">{img(i["src"], "Плитка «" + p["name"] + "» после укладки", i["w"], i["h"], "(max-width: 600px) 70vw, 320px", widths=(480, 960))}</a>'
            for i in album["images"][:10]) + "</div></section>"
    related = [x for x in P if x["category"] == c and x["slug"] != p["slug"]]
    related = sorted(related, key=lambda x: (abs(x["price"] - p["price"]), x["id"]))[:4]
    rel = "".join(card(x) for x in related)
    h1 = f"{p_title(p)} {dims(p['size'])}" if dims(p["size"]) not in p["name"].replace("х", "×") else p_title(p)
    calc_hint = {"area": "Укажите площадь — посчитаем количество плиток и сумму.",
                 "length": f"Укажите длину в метрах — посчитаем, сколько штук нужно (длина изделия {p.get('lengthMm')} мм).",
                 "qty": "Укажите количество — посчитаем сумму."}[p["calc"]]
    body = f'''<section class="prod">
  <div class="wrap prod__in">
    <div class="pg" data-gallery>
      <a class="pg__main" href="{main["src"]}-1600.webp" data-lightbox="p" data-cap="{esc(p_title(p))}">{img(main["src"], p_title(p) + " — фото", main["w"], main["h"], "(max-width: 900px) 100vw, 560px", lazy=False)}</a>
      {thumbs}
    </div>
    <div class="prod__info">
      <p class="eyebrow"><a href="{cat_url(c)}">{CATS[c]["name"]}</a></p>
      <h1 class="h1 h1--prod">{esc(h1)}</h1>
      {price_html(p, big=True)}
      <div class="prod__colors"><span>Цвета:</span>{swatches(p, big=True)}<span class="prod__cn">{", ".join(COLORS[x]["name"].lower() for x in p["colors"])}</span></div>
      <table class="spec">{spec}</table>
      <div class="prod__btns">
        <button class="btn btn--accent btn--lg" type="button" data-open-form data-subject="Заказ: {esc(p_title(p))}">Заказать</button>
        <a class="btn btn--line btn--lg" href="tel:{C["phone"]}" data-goal="phone">{C["phoneDisplay"]}</a>
      </div>
      <div class="prod__msg">{messenger_links("chip")}</div>
      <ul class="prod__ticks"><li>{icon("check")}Цена производителя, без наценок</li><li>{icon("check")}Доставка манипулятором по Перми и краю</li><li>{icon("check")}Гарантия 1 год</li></ul>
    </div>
  </div>
</section>
<section class="sec sec--tint" id="calc"><div class="wrap calc-sec__in">
  <div class="calc-sec__txt"><h2 class="h2 h2--sm">Калькулятор «{esc(p["name"])}»</h2><p>{calc_hint}</p></div>
  <div class="calc-sec__box">{calculator(p)}</div>
</div></section>
{works}
<section class="sec"><div class="wrap"><div class="sec__head"><h2 class="h2 h2--sm">Похожие модели</h2><a class="more" href="{cat_url(c)}">Все: {CATS[c]["short"].lower()} {icon("arrow")}</a></div><div class="grid">{rel}</div></div></section>
{cta_band()}'''
    title = f"{p_title(p)} {dims(p['size'])} — {money(p['price'])} ₽/{u} | Тротуарка59"
    if len(title) > 70:
        title = f"{p_title(p)} — цена {money(p['price'])} ₽/{u} | Тротуарка59"
    if len(title) > 70:
        title = f"{p_title(p)} — {money(p['price'])} ₽/{u}"
    return page(p_url(p), title, product_desc(p), body, ld=[product_ld(p)],
                og_img=main["src"] + "-960.webp",
                crumbs=[("Главная", "/"), ("Каталог", "/catalog"), (CATS[c]["name"], cat_url(c)), (p["name"], p_url(p))])


def gallery_page():
    chips = '<button type="button" class="chip-f is-on" data-album="">Все</button>' + "".join(
        f'<button type="button" class="chip-f" data-album="{a["product"] or "kamen-lomanyj"}">{esc(a["name"])} <span>{len(a["images"])}</span></button>' for a in G)
    tiles = ""
    for a in G:
        key = a["product"] or "kamen-lomanyj"
        link = f'<a class="album__link" href="/catalog/{a["product"]}">Модель «{esc(a["name"])}» в каталоге {icon("arrow")}</a>' if a["product"] else ""
        pics = "".join(f'<a class="ph" href="{i["src"]}-1600.webp" data-lightbox="g-{key}" data-cap="{esc(a["name"])}">{img(i["src"], "Плитка «" + a["name"] + "» — фото готовой работы " + str(k + 1), i["w"], i["h"], "(max-width: 600px) 50vw, 25vw", widths=(480, 960))}</a>' for k, i in enumerate(a["images"]))
        tiles += f'<section class="album" id="{key}" data-album-sec="{key}"><div class="sec__head"><h2 class="h2 h2--sm">{esc(a["name"])}</h2>{link}</div><div class="phs">{pics}</div></section>'
    total = sum(len(a["images"]) for a in G)
    body = f'''<section class="page-head"><div class="wrap">
  <h1 class="h1 h1--page">Наши работы: плитка после укладки</h1>
  <p class="page-head__lead">{total} фото дорожек, дворов и площадок, выложенных из нашей плитки. Нажмите на фото, чтобы рассмотреть его ближе.</p>
</div></section>
<section class="sec sec--top0"><div class="wrap"><div class="filters"><nav class="filters__cats" data-albums aria-label="Модели">{chips}</nav></div>{tiles}</div></section>
{cta_band("Понравилась плитка на фото?", "Оставьте заявку — подскажем модель, цвет и посчитаем количество для вашего участка.")}'''
    return page("/gallery", "Фото укладки тротуарной плитки — наши работы | Тротуарка59",
                f"{total} фото дорожек и дворов из плитки нашего производства: «Антик», «Ракушка», «Мостовая», «Клевер краковский». Пермь и Пермский край.",
                body, crumbs=[("Главная", "/"), ("Наши работы", "/gallery")])


DELIVERY_FAQ = [
    {"q": "Сколько стоит доставка плитки?", "a": "Стоимость доставки рассчитывается индивидуально: она зависит от расстояния, объёма заказа и сложности подъезда. Позвоните или оставьте заявку — назовём цену для вашего адреса."},
    {"q": "Кто выгружает плитку?", "a": "Машина с краном-манипулятором сама грузит, перевозит и выгружает поддоны. Не нужно заказывать отдельную технику и искать грузчиков."},
    {"q": "Как упакована продукция?", "a": "Вся продукция уложена на поддоны и обёрнута упаковочной плёнкой — так она не бьётся при перевозке и её удобно хранить на участке."},
]


def delivery_page():
    body = f'''<section class="page-head"><div class="wrap">
  <h1 class="h1 h1--page">Доставка плитки и бордюров манипулятором</h1>
  <p class="page-head__lead">Привезём заказ по Перми, Краснокамску и Пермскому краю автомобилем с краном-манипулятором. Стоимость считаем индивидуально — по расстоянию, объёму и подъезду.</p>
</div></section>
<section class="sec sec--top0"><div class="wrap split">
  <div class="split__txt prose">
    <h2 class="h2 h2--sm">Одна машина вместо двух</h2>
    <p>Мы предлагаем доставку нашей продукции автотранспортом с краном-манипулятором. Он совмещает транспорт и грузоподъёмное средство, поэтому вам не нужно искать и оплачивать две единицы техники и людей для разгрузки. Одна машина грузит, перевозит и выгружает ваш заказ.</p>
    <h2 class="h2 h2--sm">Упаковка</h2>
    <p>Для удобства доставки вся продукция упакована на поддонах и обёрнута упаковочной плёнкой.</p>
    <h2 class="h2 h2--sm">Стоимость</h2>
    <p>Стоимость доставки рассчитывается индивидуально и зависит от расстояния, объёма заказа и сложности подъезда. Назовите адрес по телефону <a href="tel:{C["phone"]}" data-goal="phone">{C["phoneDisplay"]}</a> или в заявке — посчитаем.</p>
    <h2 class="h2 h2--sm">Откуда отгружаем</h2>
    <p>Склад готовой продукции — {esc(C["address"]["full"])}. Работаем {esc(C["hours"].replace("Пн–Сб", "с понедельника по субботу,"))}.</p>
  </div>
  <figure class="split__pic">{img("/img/site/sklad", "Погрузка поддонов с плиткой манипулятором на складе в Краснокамске", 1440, 1080, "(max-width: 900px) 100vw, 50vw", widths=(960, 1600))}<figcaption>Погрузка на нашем складе в Краснокамске</figcaption></figure>
</div></section>
{faq_html(DELIVERY_FAQ, "Вопросы о доставке")}
{cta_band("Рассчитаем доставку на ваш адрес", "Оставьте телефон и адрес — посчитаем стоимость плитки вместе с доставкой.")}'''
    return page("/delivery", "Доставка тротуарной плитки манипулятором по Перми | Тротуарка59",
                "Доставка тротуарной плитки, бордюров и фасадной плитки по Перми, Краснокамску и краю автомобилем с краном-манипулятором. Продукция на поддонах в плёнке.",
                body, ld=[faq_ld(DELIVERY_FAQ)], crumbs=[("Главная", "/"), ("Доставка", "/delivery")])


def about_page():
    docs = "".join(f'<a class="doc" href="/img/docs/{k}-1200.webp" data-lightbox="docs" data-cap="Протокол испытаний, лист {k}">{img(f"/img/docs/{k}", f"Протокол испытаний, лист {k}", 1755, 1240, "(max-width: 600px) 100vw, 33vw", widths=(480, 1200))}</a>' for k in (1, 2, 3))
    ben = "".join(f'<li class="ben">{icon(b["icon"], "ben__ic")}<h3>{esc(b["title"])}</h3><p>{esc(fmt(b["text"]))}</p></li>' for b in T["benefits"])
    body = f'''<section class="page-head"><div class="wrap">
  <h1 class="h1 h1--page">О компании: производство бетонных изделий в Краснокамске</h1>
  <p class="page-head__lead">Наша компания уже долгое время работает на рынке строительных материалов Перми. Мы производим и продаём тротуарную и фасадную плитку и бордюры в Перми и Пермском крае, а также доставляем свою продукцию.</p>
</div></section>
<section class="sec sec--top0"><div class="wrap split">
  <div class="split__txt prose">
    <h2 class="h2 h2--sm">О продукции</h2>
    <p>Продукция производится на основе отсева гравийного щебня — это армирует изделие и кратно добавляет прочность.</p>
    <p>Выпускаем {FACTS["count_text"]}: тротуарную плитку разных форм и размеров, фасадную плитку под камень, садовые и метровые бордюры, водосточные желоба и козырьки. Основные цвета — серый, чёрный, жёлтый, красный, коричневый, у части моделей есть синий.</p>
    <p>На всю выпускаемую продукцию даём гарантию 1 год. Вся продукция проходит контроль качества на соответствие изделия ГОСТу.</p>
  </div>
  <figure class="split__pic">{img("/img/site/about", "Сырьё для производства — отсев гравийного щебня, на фоне поддоны с готовой плиткой", 1152, 864, "(max-width: 900px) 100vw, 50vw", widths=(960, 1600))}<figcaption>Отсев гравийного щебня — основа нашей плитки</figcaption></figure>
</div></section>
<section class="sec sec--tint"><div class="wrap"><h2 class="h2">Наши преимущества</h2><ul class="bens">{ben}</ul></div></section>
<section class="sec"><div class="wrap"><h2 class="h2">Протоколы испытаний</h2><div class="docs">{docs}</div></div></section>
<section class="sec sec--tint"><div class="wrap req">
  <h2 class="h2 h2--sm">Реквизиты</h2>
  <dl><dt>Продавец</dt><dd>{esc(C["legalName"])}</dd><dt>ИНН</dt><dd>{C["inn"]}</dd><dt>ОГРНИП</dt><dd>{C["ogrnip"]}</dd><dt>Адрес</dt><dd>{esc(C["address"]["full"])}</dd></dl>
</div></section>
{cta_band()}'''
    return page("/about", "О компании — производитель плитки в Краснокамске | Тротуарка59",
                "Производство тротуарной, фасадной плитки и бордюров в Краснокамске: плитка на основе отсева гравийного щебня, контроль качества, гарантия 1 год, протоколы испытаний.",
                body, crumbs=[("Главная", "/"), ("О компании", "/about")])


def contacts_page():
    q = quote(f"{C['address']['full']}, {C['address']['region']}")
    body = f'''<section class="page-head"><div class="wrap">
  <h1 class="h1 h1--page">Контакты</h1>
  <p class="page-head__lead">Звоните или пишите в мессенджеры — подскажем по наличию, цветам и рассчитаем доставку. {esc(C["hours"])}.</p>
</div></section>
<section class="sec sec--top0"><div class="wrap contacts">
  <div class="contacts__cards">
    <div class="cc"><p class="cc__l">Телефон</p><a class="cc__v" href="tel:{C["phone"]}" data-goal="phone">{C["phoneDisplay"]}</a></div>
    <div class="cc"><p class="cc__l">Мессенджеры</p><div class="cc__msg">{messenger_links("chip")}</div></div>
    <div class="cc"><p class="cc__l">Почта</p><a class="cc__v cc__v--sm" href="mailto:{C["email"]}" data-goal="email">{C["email"]}</a></div>
    <div class="cc"><p class="cc__l">Адрес склада и производства</p><p class="cc__v cc__v--sm">{esc(C["address"]["full"])}</p><p class="cc__s">{esc(C["hours"])}</p></div>
    <div class="cc"><p class="cc__l">Реквизиты</p><p class="cc__s">{esc(C["legalName"])}<br>ИНН {C["inn"]}<br>ОГРНИП {C["ogrnip"]}</p></div>
  </div>
  <div class="map" data-map="https://yandex.ru/map-widget/v1/?text={q}&amp;z=16">
    <button class="btn btn--dark" type="button" data-map-load>Показать на карте</button>
    <a class="map__link" href="https://yandex.ru/maps/?text={q}" target="_blank" rel="noopener">Открыть в Яндекс Картах</a>
  </div>
</div></section>
{cta_band("Оставьте заявку", "Перезвоним в рабочее время, ответим на вопросы и посчитаем заказ.")}'''
    return page("/contacts", "Контакты — Тротуарка59, Краснокамск, ул. Трубная, 3б",
                f"Телефон {C['phoneDisplay']}, WhatsApp, Telegram, MAX. Склад и производство: {C['address']['full']}. {C['hours']}.",
                body, ld=[org_ld()], crumbs=[("Главная", "/"), ("Контакты", "/contacts")])


def privacy_page():
    body = f'''<section class="page-head"><div class="wrap wrap--narrow"><h1 class="h1 h1--page">Политика конфиденциальности</h1>
<p class="page-head__lead">Как сайт {esc(C["siteHost"])} обрабатывает персональные данные посетителей.</p></div></section>
<section class="sec sec--top0"><div class="wrap wrap--narrow prose">
<h2>1. Оператор</h2>
<p>Оператор персональных данных — {esc(C["legalName"])} (ИНН {C["inn"]}, ОГРНИП {C["ogrnip"]}), адрес: {esc(C["address"]["full"])}, {esc(C["address"]["region"])}. Электронная почта для обращений: <a href="mailto:{C["email"]}">{C["email"]}</a>. Политика составлена в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных».</p>
<h2>2. Какие данные мы получаем</h2>
<p>Через формы на сайте вы можете передать имя, номер телефона и текст комментария (например, модель плитки и адрес доставки). Другие персональные данные через сайт не собираются.</p>
<h2>3. Зачем</h2>
<p>Данные используются только для того, чтобы связаться с вами, ответить на вопрос, рассчитать стоимость и оформить заказ. Мы не передаём их третьим лицам, кроме случаев, предусмотренных законом.</p>
<h2>4. Основание и срок</h2>
<p>Основание — ваше согласие, которое вы даёте, отмечая галочку в форме. Данные хранятся до достижения цели обработки, но не дольше 3 лет с момента последнего обращения, либо до отзыва согласия.</p>
<h2>5. Ваши права</h2>
<p>Вы можете запросить сведения о своих данных, потребовать их уточнения или удаления и отозвать согласие, написав на <a href="mailto:{C["email"]}">{C["email"]}</a>. Мы ответим в течение 10 рабочих дней.</p>
<h2>6. Cookie и сторонние сервисы</h2>
<p>Сайт использует cookie, необходимые для его работы (например, чтобы запомнить, что вы закрыли уведомление). Если вы нажмёте «Показать на карте» на странице контактов, загрузится виджет Яндекс Карт, который может устанавливать собственные cookie. Вы можете отключить cookie в настройках браузера.</p>
<h2>7. Защита данных</h2>
<p>Сайт работает по защищённому протоколу HTTPS. Доступ к заявкам есть только у сотрудников, которые обрабатывают заказы.</p>
<p class="muted">Редакция от {date.today().strftime("%d.%m.%Y")}.</p>
</div></section>'''
    return page("/politika-konfidentsialnosti", "Политика конфиденциальности | Тротуарка59",
                f"Политика обработки персональных данных на сайте {C['siteHost']}: какие данные собираются через формы, зачем и как отозвать согласие.",
                body, crumbs=[("Главная", "/"), ("Политика конфиденциальности", "/politika-konfidentsialnosti")])


def not_found():
    body = f'''<section class="nf"><div class="wrap">
  <p class="nf__code">404</p>
  <h1 class="h1 h1--page">Страница не найдена</h1>
  <p>Возможно, модель переименована или страница переехала. Загляните в каталог или позвоните: <a href="tel:{C["phone"]}">{C["phoneDisplay"]}</a></p>
  <p><a class="btn btn--accent" href="/catalog">Перейти в каталог</a> <a class="btn btn--line" href="/">На главную</a></p>
</div></section>'''
    out = page("/404", "Страница не найдена | Тротуарка59", "Страница не найдена.", body)
    return out.replace('<link rel="canonical"', '<meta name="robots" content="noindex"><link rel="canonical"', 1)


# ---------- service files ----------

def sitemap(paths):
    today = date.today().isoformat()
    urls = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{today}</lastmod></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'


def robots():
    return f"""User-agent: *
Allow: /
Disallow: /*?*utm_
Disallow: /*?*yclid=

Sitemap: {SITE}/sitemap.xml
"""


def llms():
    lines = [f"# {C['brand']} ({C['siteHost']})", "", f"> {C['tagline']}. {C['legalName']}, производство и склад: {C['address']['full']}.", "",
             f"- Телефон: {C['phoneDisplay']}; e-mail: {C['email']}; режим работы: {C['hours']}.",
             "- Тротуарная и фасадная плитка продаются за м², бордюры, желоба и козырьки — поштучно.",
             "- Доставка автомобилем с краном-манипулятором по Перми, Краснокамску и Пермскому краю; стоимость рассчитывается индивидуально.",
             "- Гарантия на продукцию — 1 год.", "", "## Разделы", ""]
    lines += [f"- [{n}]({SITE}{u})" for u, n in NAV]
    lines += ["", "## Каталог и цены", ""]
    for c, d in CATS.items():
        lines.append(f"### {d['name']}")
        for p in P:
            if p["category"] == c:
                col = f", цветная {p['priceColor']} ₽/{unit(p)}" if has_color(p) else ""
                lines.append(f"- [{p_title(p)}]({SITE}{p_url(p)}): {dims(p['size'])} мм, {p['price']} ₽/{unit(p)} серая{col}")
        lines.append("")
    return "\n".join(lines)


# ---------- main ----------

def write(path, content):
    fn = os.path.join(DIST, *path.strip("/").split("/")) if path.strip("/") else os.path.join(DIST, "index")
    fn += ".html" if not os.path.splitext(fn)[1] else ""
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    with open(fn, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def strip_comments(s):
    return re.sub(r"<!--(?!\[).*?-->", "", s, flags=re.S)


def staging(s):
    """Копия в подпапке (GitHub Pages): префикс у корневых путей, закрыта от индексации.
    canonical и og:url остаются на боевом домене — они абсолютные и не затрагиваются."""
    if BASE:
        s = re.sub(r'(\s(?:href|src|data-src)=")/(?!/)', rf"\1{BASE}/", s)
        s = re.sub(r'(srcset="|, )/img/', rf"\1{BASE}/img/", s)
    if STAGING:
        s = s.replace('<meta name="viewport"', '<meta name="robots" content="noindex, nofollow">\n<meta name="viewport"', 1)
    return s


LOGO = open(os.path.join(ROOT, "static", "img", "logo.svg"), encoding="utf-8").read().replace("<svg", '<svg role="img" aria-hidden="true"', 1)


def main():
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    shutil.copytree(os.path.join(ROOT, "static"), DIST)
    pages = {"/": home(), "/catalog": catalog_page()}
    for c in CATS:
        pages[cat_url(c)] = category_page(c)
    for p in P:
        pages[p_url(p)] = product_page(p)
    pages["/gallery"] = gallery_page()
    pages["/delivery"] = delivery_page()
    pages["/about"] = about_page()
    pages["/contacts"] = contacts_page()
    pages["/politika-konfidentsialnosti"] = privacy_page()
    for path, content in pages.items():
        write(path, staging(strip_comments(content)))
    write("/404", staging(not_found()))
    if BASE:
        # /catalog — и файл, и папка; GitHub Pages может увести на /catalog/ — кладём копию туда
        write("/catalog/index", staging(strip_comments(pages["/catalog"])))
        css = os.path.join(DIST, "css", "style.css")
        t = open(css, encoding="utf-8").read().replace("url(/", f"url({BASE}/")
        open(css, "w", encoding="utf-8", newline="\n").write(t)
    with open(os.path.join(DIST, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap(pages.keys()))
    with open(os.path.join(DIST, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots())
    with open(os.path.join(DIST, "llms.txt"), "w", encoding="utf-8") as f:
        f.write(llms())
    with open(os.path.join(DIST, "products.json"), "w", encoding="utf-8") as f:
        json.dump(calc_data(), f, ensure_ascii=False)
    todos = sorted(set(TODOS))
    if not C.get("formEndpoint"):
        todos.append("Адрес приёма заявок (formEndpoint): куда отправлять формы")
    print(f"Собрано страниц: {len(pages) + 1} → {DIST}")
    if todos:
        print("Не хватает от клиента:\n  - " + "\n  - ".join(todos))
        if PROD:
            raise SystemExit("Прод-сборка остановлена: заполните факты выше в data/company.json")


if __name__ == "__main__":
    main()
