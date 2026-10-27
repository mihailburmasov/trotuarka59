(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var CFG = window.SITE || {};
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  function goal(name) { if (window.ym && window.YM_ID) window.ym(window.YM_ID, "reachGoal", name); }
  function money(n) { return Math.round(n).toLocaleString("ru-RU").replace(/,/g, " "); }

  // ----- меню -----
  var burger = $(".burger"), nav = $("#nav");
  if (burger && nav) {
    burger.addEventListener("click", function () {
      var open = burger.getAttribute("aria-expanded") !== "true";
      burger.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
    });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) { burger.setAttribute("aria-expanded", "false"); nav.classList.remove("is-open"); } });
  }

  // ----- цели Метрики на кликах -----
  document.addEventListener("click", function (e) {
    var a = e.target.closest("[data-goal]");
    if (a) goal(a.getAttribute("data-goal"));
  });

  // ----- cookie -----
  var cookie = $(".cookie");
  if (cookie && !store.get("cookie-ok")) cookie.hidden = false;
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-cookie-ok]")) { store.set("cookie-ok", "1"); cookie.hidden = true; }
  });

  // ----- модальные окна -----
  var modal = $("#lead-modal");
  function openForm(subject, comment) {
    if (!modal) return;
    var f = $("form", modal);
    f.subject.value = subject || "Заявка с сайта";
    if (comment) f.comment.value = comment;
    if (modal.showModal) modal.showModal(); else modal.setAttribute("open", "");
    setTimeout(function () { (f.phone).focus(); }, 50);
    goal("form_open");
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-open-form]");
    if (b) { e.preventDefault(); openForm(b.getAttribute("data-subject")); }
    var x = e.target.closest("[data-close]");
    if (x) x.closest("dialog").close();
  });
  $$("dialog").forEach(function (d) {
    d.addEventListener("click", function (e) { if (e.target === d) d.close(); });
  });

  // ----- формы заявок -----
  $$("form[data-lead]").forEach(function (f) {
    var status = $(".lead__status", f);
    f.phone.addEventListener("input", function () { f.phone.closest(".fld").classList.remove("is-invalid"); });
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      status.className = "lead__status";
      var digits = f.phone.value.replace(/\D/g, "");
      if (digits.length < 10) {
        f.phone.closest(".fld").classList.add("is-invalid");
        status.className = "lead__status is-err";
        status.textContent = "Укажите номер телефона полностью.";
        f.phone.focus();
        return;
      }
      if (!f.consent.checked) {
        status.className = "lead__status is-err";
        status.textContent = "Нужно согласие на обработку персональных данных.";
        return;
      }
      if (f.website.value) return; // ловушка для ботов
      if (!CFG.endpoint) {
        // приём заявок ещё не подключён — не делаем вид, что заявка ушла
        status.className = "lead__status is-demo";
        status.innerHTML = "Это демо-версия сайта, заявки пока не принимаются. Позвоните нам: <a href=\"tel:" + CFG.tel + "\">" + CFG.phone + "</a>";
        return;
      }
      var btn = $("button[type=submit]", f);
      btn.disabled = true;
      var data = new FormData(f);
      data.append("page", location.pathname);
      fetch(CFG.endpoint, { method: "POST", body: data })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r; })
        .then(function () {
          status.className = "lead__status is-ok";
          status.textContent = "Спасибо! Заявка отправлена — перезвоним в рабочее время.";
          f.reset(); f.consent.checked = true;
          goal("lead");
        })
        .catch(function () {
          status.className = "lead__status is-err";
          status.innerHTML = "Не удалось отправить. Позвоните: <a href=\"tel:" + CFG.tel + "\">" + CFG.phone + "</a>";
        })
        .then(function () { btn.disabled = false; });
    });
  });

  // ----- калькулятор -----
  $$("form[data-calc]").forEach(function (f) {
    var dataEl = f.previousElementSibling;
    var list = JSON.parse(dataEl.textContent);
    var fixed = f.getAttribute("data-product");
    var colorBox = $("[data-color]", f);
    var out = {
      need: $("[data-out=need]", f), pcs: $("[data-out=pcs]", f), sum: $("[data-out=sum]", f)
    };
    function current() {
      var slug = fixed || f.product.value;
      for (var i = 0; i < list.length; i++) if (list[i].slug === slug) return list[i];
      return list[0];
    }
    function num(v) { var n = parseFloat(String(v).replace(",", ".")); return isFinite(n) && n > 0 ? n : 0; }
    function render() {
      var p = current();
      $$("[data-for]", f).forEach(function (el) { el.hidden = el.getAttribute("data-for") !== p.calc; });
      colorBox.hidden = !p.priceColor;
      if (!p.priceColor) f.color.value = "grey";
      var price = f.color.value === "color" && p.priceColor ? p.priceColor : p.price;
      var u = p.unit === "m2" ? "м²" : "шт";
      var total = 0, need = "", pcs = "";
      if (p.calc === "area") {
        var area = num(f.area.value), res = parseFloat(f.reserve.value) || 0;
        var m2 = Math.ceil(area * (1 + res / 100) * 10) / 10;
        total = m2 * price;
        need = "С запасом: <b>" + String(m2).replace(".", ",") + " м²</b> × " + money(price) + " ₽";
        pcs = p.perM2 ? "Это примерно <b>" + money(Math.ceil(m2 * p.perM2)) + " шт</b> плитки (" + p.perM2 + " шт в 1 м²)" : "";
      } else if (p.calc === "length") {
        var len = num(f.meters.value);
        var n = p.lengthMm ? Math.ceil(len * 1000 / p.lengthMm) : 0;
        total = n * price;
        need = "Нужно: <b>" + money(n) + " шт</b> × " + money(price) + " ₽/шт";
        pcs = "Длина одного изделия — " + p.lengthMm + " мм";
      } else {
        var q = Math.ceil(num(f.qty.value));
        total = q * price;
        need = "<b>" + money(q) + " шт</b> × " + money(price) + " ₽/шт";
      }
      out.need.innerHTML = need;
      out.pcs.innerHTML = pcs;
      out.pcs.hidden = !pcs;
      out.sum.textContent = "≈ " + money(total) + " ₽";
      f._summary = p.name + ": " + out.need.textContent + (pcs ? "; " + out.pcs.textContent : "") + "; итого ≈ " + money(total) + " ₽ (" + (f.color.value === "color" ? "цветной" : "серый") + ", цена за " + u + ")";
    }
    f.addEventListener("input", render);
    f.addEventListener("change", render);
    $("[data-calc-send]", f).addEventListener("click", function () { goal("calc_send"); openForm("Расчёт из калькулятора", f._summary); });
    render();
  });

  // ----- фильтры каталога -----
  var filters = $("[data-filters]");
  if (filters) {
    var cards = $$(".card");
    var empty = $(".filters__empty", filters);
    var sortSel = $("[data-sort]", filters);
    var grids = $$(".grid").filter(function (g) { return g.querySelector(".card"); });
    grids.forEach(function (g) { $$(".card", g).forEach(function (c, i) { c._i = i; }); });
    var apply = function () {
      var want = $$(".filters__colors input:checked", filters).map(function (i) { return i.value; });
      var shown = 0;
      cards.forEach(function (c) {
        var cs = c.getAttribute("data-colors").split(" ");
        var ok = !want.length || want.every(function (w) { return cs.indexOf(w) >= 0; });
        c.hidden = !ok; if (ok) shown++;
      });
      $$(".cat-sec").forEach(function (s) { s.hidden = !$(".card:not([hidden])", s); });
      empty.hidden = shown > 0;
      var dir = sortSel.value;
      grids.forEach(function (g) {
        $$(".card", g).sort(function (a, b) {
          if (!dir) return a._i - b._i;
          var d = +a.getAttribute("data-price") - +b.getAttribute("data-price");
          return dir === "asc" ? d : -d;
        }).forEach(function (c) { g.appendChild(c); });
      });
    };
    filters.addEventListener("change", apply);
    $("[data-reset]", filters).addEventListener("click", function () {
      $$(".filters__colors input", filters).forEach(function (i) { i.checked = false; }); apply();
    });
  }

  // ----- альбомы галереи -----
  var albums = $("[data-albums]");
  if (albums) {
    var setAlbum = function (key) {
      $$("[data-album]", albums).forEach(function (b) { b.classList.toggle("is-on", b.getAttribute("data-album") === key); });
      $$("[data-album-sec]").forEach(function (s) { s.hidden = key && s.getAttribute("data-album-sec") !== key; });
    };
    albums.addEventListener("click", function (e) {
      var b = e.target.closest("[data-album]"); if (!b) return;
      var key = b.getAttribute("data-album"); setAlbum(key);
      history.replaceState(null, "", key ? "#" + key : location.pathname);
    });
    var h = location.hash.slice(1);
    if (h && $("[data-album-sec=\"" + h + "\"]")) setAlbum(h);
  }

  // ----- галерея товара -----
  var pg = $("[data-gallery]");
  if (pg) {
    var mainA = $(".pg__main", pg), mainImg = $("img", mainA);
    pg.addEventListener("click", function (e) {
      var t = e.target.closest(".pg__t"); if (!t) return;
      var s = t.getAttribute("data-src");
      mainImg.src = s + "-960.webp";
      mainImg.srcset = s + "-480.webp 480w, " + s + "-960.webp 960w, " + s + "-1600.webp 1600w";
      mainA.href = s + "-1600.webp";
      $$(".pg__t", pg).forEach(function (x) { x.classList.toggle("is-on", x === t); });
    });
  }

  // ----- лайтбокс -----
  var lb = $("#lightbox");
  if (lb) {
    var lbImg = $("img", lb), lbCap = $(".lightbox__cap", lb), group = [], idx = 0;
    var show = function (i) {
      idx = (i + group.length) % group.length;
      var a = group[idx];
      lbImg.src = a.href;
      lbImg.alt = (a.querySelector("img") || {}).alt || "";
      lbCap.textContent = (a.getAttribute("data-cap") || "") + (group.length > 1 ? " · " + (idx + 1) + " из " + group.length : "");
    };
    document.addEventListener("click", function (e) {
      var a = e.target.closest("a[data-lightbox]");
      if (!a || !lb.showModal) return;
      e.preventDefault();
      var g = a.getAttribute("data-lightbox");
      group = $$("a[data-lightbox=\"" + g + "\"]");
      if (a.classList.contains("pg__main")) {
        group = $$(".pg__t", pg).map(function (t) { return { href: t.getAttribute("data-src") + "-1600.webp", getAttribute: function () { return a.getAttribute("data-cap"); }, querySelector: function () { return null; } }; });
        if (!group.length) group = [a];
        idx = Math.max(0, $$(".pg__t", pg).findIndex(function (t) { return t.classList.contains("is-on"); }));
        lb.showModal(); show(idx); return;
      }
      lb.showModal(); show(group.indexOf(a));
    });
    $(".lightbox__prev", lb).addEventListener("click", function () { show(idx - 1); });
    $(".lightbox__next", lb).addEventListener("click", function () { show(idx + 1); });
    lb.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") show(idx - 1);
      if (e.key === "ArrowRight") show(idx + 1);
    });
  }

  // ----- карта по клику (без cookie Яндекса до действия пользователя) -----
  var map = $("[data-map]");
  if (map) {
    $("[data-map-load]", map).addEventListener("click", function () {
      var f = document.createElement("iframe");
      f.src = map.getAttribute("data-map");
      f.title = "Карта: склад и производство";
      f.loading = "lazy";
      map.appendChild(f);
    });
  }

  // ----- появление при прокрутке -----
  var rv = $$(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    rv.forEach(function (el) { io.observe(el); });
  } else rv.forEach(function (el) { el.classList.add("is-in"); });
})();
