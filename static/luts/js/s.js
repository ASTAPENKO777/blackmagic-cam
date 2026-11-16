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

  // Кнопки в Telegram: t.me/<bot>?start=web_<src>__<slug>, не довше 64 символів (інакше без slug).
  document.querySelectorAll("a[data-tg]").forEach((a) => {
    const s = a.dataset.slug;
    let p = `web_${src || "site"}__${s}`;
    if (p.length > 64) p = `web_${src || "site"}`.slice(0, 64);
    a.href = `https://t.me/${BOT}?start=${p}`;
    a.addEventListener("click", () => send("tg_click", s));
  });

  // Слайдер: ручка рухає --pos; перший дотик рахуємо подією, підказка зникає.
  let slid = false;
  document.querySelectorAll("[data-ba]").forEach((ba) => {
    const range = ba.querySelector(".ba-range");
    range.addEventListener("input", () => {
      ba.style.setProperty("--pos", range.value + "%");
      ba.classList.add("touched");
      if (!slid) { slid = true; send("slider", slug); }
    });
  });
  if ("IntersectionObserver" in window) {
    const wink = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("wink"); wink.unobserve(e.target); }
    }), { threshold: 0.6 });
    const first = document.querySelector("[data-ba]");
    if (first) wink.observe(first);

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

  // Портфоліо: відео вантажиться й грає лише коли в кадрі; без руху при prefers-reduced-motion.
  const still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  if ("IntersectionObserver" in window && !still) {
    const vids = new IntersectionObserver((es) => es.forEach((e) => {
      const v = e.target;
      if (e.isIntersecting) { if (!v.src) v.src = v.dataset.src; v.play().catch(() => {}); } else { v.pause(); }
    }), { threshold: 0.35 });
    document.querySelectorAll("video[data-src]").forEach((v) => vids.observe(v));
  }

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
