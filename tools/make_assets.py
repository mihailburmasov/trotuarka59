"""Фавиконки и картинка для соцсетей (og.jpg 1200×630). Запуск: python -I tools/make_assets.py"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "static", "img")
DARK, ACCENT, OCHRE = (35, 33, 30), (180, 67, 42), (217, 160, 58)

# значок: четыре плитки «в перевязку»
svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#23211e"/>
<rect x="10" y="12" width="26" height="12" rx="2" fill="#b4432a"/><rect x="39" y="12" width="15" height="12" rx="2" fill="#d9a03a"/>
<rect x="10" y="27" width="12" height="12" rx="2" fill="#d9a03a"/><rect x="25" y="27" width="29" height="12" rx="2" fill="#b4432a"/>
<rect x="10" y="42" width="26" height="12" rx="2" fill="#b4432a"/><rect x="39" y="42" width="15" height="12" rx="2" fill="#a3a19b"/></svg>"""
open(os.path.join(IMG, "favicon.svg"), "w", encoding="utf-8").write(svg)


def icon(size):
    k = size / 64
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=round(12 * k), fill=DARK)
    for x, y, w, h, c in [(10, 12, 26, 12, ACCENT), (39, 12, 15, 12, OCHRE), (10, 27, 12, 12, OCHRE),
                          (25, 27, 29, 12, ACCENT), (10, 42, 26, 12, ACCENT), (39, 42, 15, 12, (163, 161, 155))]:
        d.rounded_rectangle([x * k, y * k, (x + w) * k, (y + h) * k], radius=max(1, round(2 * k)), fill=c)
    return im


icon(256).save(os.path.join(ROOT, "static", "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
icon(180).convert("RGB").save(os.path.join(IMG, "apple-touch-icon.png"))

# og.jpg: фото работы + плашка с текстом
src = Image.open(os.path.join(IMG, "gallery", "antik", "5-1600.webp")).convert("RGB")
W, H = 1200, 630
k = max(W / src.width, H / src.height)
src = src.resize((round(src.width * k), round(src.height * k)), Image.LANCZOS)
top = (src.height - H) // 2
og = src.crop((0, top, W, top + H))
shade = Image.new("RGB", (W, H), DARK)
mask = Image.linear_gradient("L").rotate(90).resize((W, H))
og = Image.composite(og, shade, mask.point(lambda v: min(255, int(v * 1.1))))
d = ImageDraw.Draw(og)
fb = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 64)
fr = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
d.rectangle([60, 120, 72, 330], fill=ACCENT)
d.text((96, 110), "ТРОТУАРНАЯ ПЛИТКА", font=fb, fill="white")
d.text((96, 186), "И БОРДЮРЫ", font=fb, fill="white")
d.text((96, 262), "от производителя в Перми", font=fr, fill=(241, 237, 230))
d.text((96, 470), "тротуарка59.рф", font=fr, fill=OCHRE)
d.text((96, 516), "+7 (965) 558-88-82", font=fr, fill="white")
og.save(os.path.join(IMG, "og.jpg"), quality=86)
print("ok")
