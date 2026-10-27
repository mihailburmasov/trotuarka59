# тротуарка59.рф — новый сайт

Статический сайт, который собирается из JSON-файлов в Python, и замена текущего Next.js-сайта. Все адреса старого сайта сохранены, поэтому вес в выдаче не теряется.

## Структура

| Путь | Что это |
|---|---|
| `data/company.json` | факты о компании: телефон, адрес, реквизиты, мессенджеры, адрес приёма заявок, ID Метрики |
| `data/products.json` | каталог из 31 позиции, импортированный со старого сайта. Поле `unit`: `m2` — плитка, `pcs` — бордюры, желоба, козырьки |
| `data/gallery.json` | альбомы «Наши работы» |
| `data/content.json` | тексты: категории, преимущества, шаги, FAQ, цвета |
| `static/` | CSS, JS, шрифты (Oswald + PT Sans, локально), картинки в WebP |
| `build.py` | сборка в `dist/` |
| `serve.py` | локальный просмотр: `python -I serve.py` → http://localhost:8059 |
| `deploy/nginx.conf` | пример конфига: адреса без `.html`, редиректы, заголовки безопасности |
| `tools/fetch_old.py`, `tools/fetch_extra.py` | загрузка данных старого сайта в `../_old`: API каталога, страницы, фото, галерея |
| `tools/import_old.py` | импорт из `../_old` в `data/` и `static/` (WebP, логотип, шрифты) |
| `tools/make_assets.py` | фавиконки и og.jpg |

## Сборка

```
python -I build.py          # стенд: незаполненные факты видны бейджем «нужно от клиента»
python -I build.py --prod   # прод: остановится, пока есть todo или не задан formEndpoint
```

## Стенд на GitHub Pages

При каждом пуше в `main` workflow `.github/workflows/pages.yml` собирает сайт командой `build.py --base /trotuarka59 --staging` и выкладывает его на
https://mihailburmasov.github.io/trotuarka59/.

Особенности стенда:
- все страницы закрыты от индексации (`noindex`);
- `canonical` указывает на боевой домен;
- форма показывает сообщение «демо-версия».

Если собираете стенд локально в Git Bash, добавьте `MSYS_NO_PATHCONV=1`, иначе Git Bash превратит `/trotuarka59` в путь Windows.

## Адреса (как на старом сайте)

`/`, `/catalog`, `/catalog/<slug>` (31 товар, те же slug), `/gallery`, `/delivery`, `/about`, `/contacts`.
Новые страницы: `/catalog/trotuarnaya-plitka`, `/catalog/fasadnaya-plitka`, `/catalog/bordyury`, `/politika-konfidentsialnosti`.
Также генерируются `sitemap.xml`, `robots.txt`, `llms.txt` и `404.html`.

## Обновить цены и фото из старой админки

Данные сняты со старого сайта 27.10.2026. Если клиент успел что-то поменять в старой админке, данные нужно перекачать:

```
python -I tools/fetch_old.py && python -I tools/fetch_extra.py   # → ../_old
python -I tools/import_old.py ../_old                              # → data/, static/
python -I build.py
```

Внимание: `import_old.py` перезаписывает `data/products.json`. Ручные правки этого файла нужно повторить.

## Перед выкладкой

1. `data/company.json` → `messengers.max`: ссылка на профиль MAX (`https://max.ru/u/…`). Ссылки на чат по номеру телефона в MAX нет.
2. `data/company.json` → `formEndpoint`: куда отправлять заявки. Пока не задан, форма честно пишет «демо-версия, позвоните».
3. `metrikaId`: ID счётчика Яндекс Метрики. На старом сайте счётчика не было. Цели уже размечены: `phone`, `whatsapp`, `telegram`, `max`, `email`, `form_open`, `calc_send`, `lead`.
4. На сервере: собрать с `--prod`, выложить `dist/`, подключить `deploy/nginx.conf`, затем проверить
   `audit_site.py тротуарка59.рф --inner 5`.
