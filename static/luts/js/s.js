/* /luts: джерело трафіку, події для статистики бота, слайдер, прилипла кнопка. Без бібліотек. */
(() => {
  const el = document.currentScript, EVENT = el.dataset.event, BOT = el.dataset.bot;
  const ok = /^[A-Za-z0-9_-]{1,40}$/;
  const cookie = (k) => (document.cookie.match(new RegExp("(?:^|; )" + k + "=([^;]*)")) || [])[1] || "";
  const setCookie = (k, v) => { try { document.cookie = `${k}=${v}; max-age=${90 * 86400}; path=/; SameSite=Lax`; } catch (e) {} };

  // Перше джерело запам'ятовуємо на 90 днів (першим виграє ?src=, далі — cookie).
  const q = new URLSearchParams(location.search).get("src");
  let src = cookie("bmc_src");
  if (!src && q && ok.test(q)) { src = q.toLowerCase(); setCookie("bmc_src", src); }
  let vid = cookie("bmc_vid");
  if (!vid) {
    const a = new Uint8Array(9); (crypto || window.msCrypto).getRandomValues(a);
    vid = Array.from(a, (b) => (b % 36).toString(36)).join("") + "x";
    setCookie("bmc_vid", vid);
  }

  const slug = document.body.dataset.slug || "";
  const send = (type, s) => {
    try { navigator.sendBeacon(EVENT, JSON.stringify({ type, vid, src: src || undefined, slug: /^[a-z0-9][a-z0-9_-]{0,40}$/.test(s) ? s : undefined })); } catch (e) {}
  };
  send("view", slug);

  // Таймкод у кадрі hero: рахує від входу на сторінку, як запис у Blackmagic Camera (24 кадри/с).
  const tc = document.querySelector("[data-tc]");
  if (tc) {
    const t0 = performance.now(), pad = (n) => String(n).padStart(2, "0");
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let last = "";
    const tick = (now) => {
      const ms = now - t0, s = Math.floor(ms / 1000);
      const v = `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}:${still ? "00" : pad(Math.floor((ms % 1000) * 24 / 1000))}`;
      if (v !== last) { tc.textContent = v; last = v; }
      if (still) setTimeout(() => tick(performance.now()), 1000 - (ms % 1000)); else requestAnimationFrame(tick);
    };
    tick(t0);
  }

  // Кнопки в Telegram: t.me/<bot>?start=web_<src>__<slug>, не довше 64 символів (інакше без slug).
  document.querySelectorAll("a[data-tg]").forEach((a) => {
    const s = a.dataset.slug;
    let p = `web_${src || "site"}__${s}`;
    if (p.length > 64) p = `web_${src || "site"}`.slice(0, 64);
    a.href = `https://t.me/${BOT}?start=${p}`;
    a.addEventListener("click", () => send("tg_click", s));
  });

  // Слайдер: ручка задає ціль, а --pos плавно доганяє її (без ривків); початок на 36%.
  // Поки людина не торкнулась, він тихо «подихає» вправо раз на ~2 с. Після першого дотику подих вимикається.
  const calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  let slid = false;
  document.querySelectorAll("[data-ba]").forEach((ba) => {
    const range = ba.querySelector(".ba-range"), BASE = 36, NUDGE = 5;
    let cur = BASE, target = BASE, ease = 0.2, raf = 0, touched = false, timer = 0, shown = false;
    const paint = () => {
      cur += (target - cur) * ease;
      if (Math.abs(target - cur) < 0.04) cur = target;
      ba.style.setProperty("--pos", cur.toFixed(2) + "%");
      raf = cur === target ? 0 : requestAnimationFrame(paint);
    };
    const go = (v, e) => { target = v; ease = e; if (!raf) raf = requestAnimationFrame(paint); };
    range.value = BASE;
    range.addEventListener("input", () => {
      touched = true; clearTimeout(timer); ba.classList.add("touched");
      go(parseFloat(range.value), 0.28);
      if (!slid) { slid = true; send("slider", slug); }
    });
    const nudge = () => {
      if (touched || !shown) return;
      go(BASE + NUDGE, 0.045);
      timer = setTimeout(() => { if (!touched) go(BASE, 0.05); timer = setTimeout(nudge, 700); }, 750);
    };
    if (!calm && "IntersectionObserver" in window) {
      new IntersectionObserver(([e]) => {
        shown = e.isIntersecting; clearTimeout(timer);
        if (shown && !touched) timer = setTimeout(nudge, 1200);
      }, { threshold: 0.5 }).observe(ba);
    }
  });
  if ("IntersectionObserver" in window) {
    // Прилипла кнопка з'являється, коли основна кнопка поза екраном.
    document.querySelectorAll("[data-sticky]").forEach((bar) => {
      const target = document.querySelector(bar.dataset.watch);
      if (!target) return;
      new IntersectionObserver(([e]) => { bar.hidden = e.isIntersecting || e.boundingClientRect.top > 0; }).observe(target);
    });
  }

  // Меню мови закривається кліком поза ним і клавішею Esc.
  const lang = document.querySelector("details.lang");
  if (lang) {
    document.addEventListener("click", (e) => { if (!lang.contains(e.target)) lang.open = false; });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") lang.open = false; });
  }

  // Записи екрана на картках і в плитках: грають лише частину з увімкненим LUT (data-start), без «LUT OFF».
  document.querySelectorAll("video[data-start]").forEach((v) => {
    const from = parseFloat(v.dataset.start) || 0;
    v.removeAttribute("loop");
    v.addEventListener("loadedmetadata", () => { v.currentTime = from; });
    v.addEventListener("ended", () => { v.currentTime = from; v.play().catch(() => {}); });
  });

  // Портфоліо: відео вантажиться й грає лише коли в кадрі; без руху при prefers-reduced-motion.
  const still = calm;
  if ("IntersectionObserver" in window && !still) {
    const vids = new IntersectionObserver((es) => es.forEach((e) => {
      const v = e.target;
      if (e.isIntersecting) { if (!v.src) v.src = v.dataset.src; v.play().catch(() => {}); } else { v.pause(); }
    }), { threshold: 0.35 });
    document.querySelectorAll("video[data-src]").forEach((v) => vids.observe(v));
  }

  // Слайдер на відео: «до» (плоска версія) і «після» грають разом; «після» веде, «до» доганяє, якщо розійшлись.
  document.querySelectorAll("[data-vba]").forEach((ba) => {
    const after = ba.querySelector("video.ba-after"), before = ba.querySelector("video.ba-before");
    setInterval(() => {
      if (after.paused || before.readyState < 2) return;
      if (Math.abs(before.currentTime - after.currentTime) > 0.12) before.currentTime = after.currentTime;
      if (before.paused) before.play().catch(() => {});
    }, 250);
  });

  // Стрілки стрічки портфоліо (на телефоні стрічка гортається пальцем).
  document.querySelectorAll("[data-rail-btn]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const rail = btn.parentElement.querySelector("[data-rail]");
      const rtl = getComputedStyle(rail).direction === "rtl";
      rail.scrollBy({ left: Number(btn.dataset.railBtn) * rail.clientWidth * 0.8 * (rtl ? -1 : 1), behavior: "smooth" });
    });
  });

  // Вбудований браузер TikTok/Instagram/Facebook: Telegram там відкривається гірше.
  if (/musical_ly|TikTok|Bytedance|Instagram|FBAN|FBAV/i.test(navigator.userAgent)) {
    const bar = document.getElementById("inapp"); if (bar) bar.hidden = false;
  }
})();
