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

  // Живі деталі. Усе вимикається при «зменшити рух» у системі.
  const noMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!noMotion && "IntersectionObserver" in window) {
    // Плавна поява блоків при скролі. Ховаємо лише те, що ще нижче екрана, тож нічого не блимає при завантаженні.
    const items = document.querySelectorAll(".sec-head, .pack-row, .single, .steps li, .faq, .foot-top > *");
    const seen = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("rv-in"); seen.unobserve(e.target); }
    }), { rootMargin: "0px 0px -8% 0px" });
    items.forEach((node) => {
      if (node.getBoundingClientRect().top < innerHeight) return;
      const row = node.parentElement ? Array.prototype.indexOf.call(node.parentElement.children, node) % 3 : 0;
      node.style.setProperty("--rv-delay", `${row * 70}ms`);
      node.classList.add("rv");
      seen.observe(node);
    });
    // «6 000+»: число набігає від нуля, коли видно панель.
    const num = document.querySelector(".st-ver bdi");
    const target = num && parseInt(num.textContent.replace(/\D/g, ""), 10);
    if (target) {
      const fmt = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0") + "+";
      const run = () => {
        const t0 = performance.now(), dur = 1400;
        const step = (now) => {
          const k = Math.min(1, (now - t0) / dur), eased = 1 - Math.pow(1 - k, 3);
          num.textContent = fmt(Math.round(target * eased / 100) * 100);
          if (k < 1) requestAnimationFrame(step); else num.textContent = fmt(target);
        };
        requestAnimationFrame(step);
      };
      const io = new IntersectionObserver((e) => { if (e[0].isIntersecting) { io.disconnect(); run(); } });
      io.observe(num);
    }
  }

  // Живі сповіщення: лише справжні події бота (покупки за Stars і отримання Starter), без імен.
  // Картка тримається ~12 с, під нею повільно спливає шкала часу (під курсором пауза), потім м'яко змінюється наступною.
  // Кожна третя — покупка, якщо вони є. Хрестик вимикає сповіщення до кінця сесії.
  const live = document.getElementById("live");
  if (live && EVENT && !sessionStorage.getItem("bmc_live_off")) {
    const d = live.dataset, titles = JSON.parse(d.titles || "{}"), HOLD = 12000, GAP = 1400;
    const freeLines = JSON.parse(d.freeLines || "[]").map((t) => t.replace("{n}", d.starterN));
    const rtf = window.Intl && Intl.RelativeTimeFormat ? new Intl.RelativeTimeFormat(d.lang, { numeric: "auto" }) : null;
    const ago = (at) => {
      const sec = Math.max(60, Date.now() / 1000 - at);
      if (!rtf) return "";
      if (sec < 3600) return rtf.format(-Math.round(sec / 60), "minute");
      if (sec < 86400) return rtf.format(-Math.round(sec / 3600), "hour");
      return rtf.format(-Math.round(sec / 86400), "day");
    };
    fetch(EVENT.replace(/\/public\/event$/, "/public/activity.json"), { mode: "cors" })
      .then((r) => (r.ok ? r.json() : { events: [] }))
      .then(({ events }) => {
        const ok = (events || []).filter((e) => e.kind === "free" || titles[e.slug]);
        if (!ok.length) return;
        const buys = ok.filter((e) => e.kind === "buy"), frees = ok.filter((e) => e.kind === "free");
        let n = 0, bi = 0, fi = 0, timer = 0, left = HOLD, started = 0, stopped = false;
        const pick = () => {
          const wantBuy = buys.length && (!frees.length || n % 3 === 2);
          n++;
          return wantBuy ? buys[bi++ % buys.length] : frees[fi++ % frees.length];
        };
        const card = document.createElement("a"), close = document.createElement("button"), bar = document.createElement("i");
        card.className = "live-card"; bar.className = "live-bar";
        close.type = "button"; close.className = "live-x"; close.setAttribute("aria-label", d.close); close.textContent = "\u00d7";
        live.append(card, close);
        live.hidden = false;
        const render = (e) => {
          const buy = e.kind === "buy";
          card.href = buy ? `${d.root}/${e.slug}` : d.freeHref;
          card.replaceChildren();
          const badge = document.createElement("span");
          badge.className = buy ? "live-ic live-buy" : "live-ic live-free";
          if (buy) badge.innerHTML = '<svg viewBox="0 0 88 84" aria-hidden="true"><use href="#tg-star-gold"/></svg>'; else badge.textContent = "FREE";
          const text = document.createElement("span");
          text.className = "live-text";
          const b = document.createElement("b"); b.textContent = buy ? titles[e.slug] : d.freeTitle;
          // «Д*** · підписник каналу · 5 годин тому»: лише перша літера імені, фрази по черзі, щоб не було однаково
          const what = buy ? d.buy : (freeLines.length ? freeLines[(n - 1) % freeLines.length] : d.free);
          const small = document.createElement("small"); small.textContent = [e.who ? `${e.who}***` : "", what, ago(e.at)].filter(Boolean).join(" · ");
          text.append(b, small);
          card.append(badge, text, bar);
        };
        const run = (ms) => {   // шкала: тривалість = скільки лишилося показу
          started = performance.now(); left = ms;
          bar.style.transition = "none"; bar.style.transform = `scaleX(${ms / HOLD})`;
          void bar.offsetWidth;
          bar.style.transition = `transform ${ms}ms linear`; bar.style.transform = "scaleX(0)";
          timer = setTimeout(swap, ms);
        };
        const show = () => { if (stopped) return; render(pick()); live.classList.add("on"); run(HOLD); };
        const swap = () => { live.classList.remove("on"); timer = setTimeout(show, GAP); };
        live.addEventListener("mouseenter", () => {   // пауза під курсором: встигнути прочитати
          if (!live.classList.contains("on")) return;
          clearTimeout(timer);
          left = Math.max(800, left - (performance.now() - started));
          bar.style.transition = "none"; bar.style.transform = `scaleX(${left / HOLD})`;
        });
        live.addEventListener("mouseleave", () => { if (live.classList.contains("on") && !stopped) run(left); });
        close.addEventListener("click", () => {
          stopped = true; clearTimeout(timer); live.classList.remove("on");
          try { sessionStorage.setItem("bmc_live_off", "1"); } catch (e) {}
        });
        timer = setTimeout(show, 4000);
      })
      .catch(() => {});
  }

  // «Свіже з каналу»: час і дати місцевою мовою; поки блок у кадрі, раз на хвилину підтягуємо нові пости, реакції й перегляди.
  const win = document.querySelector(".tg-window");
  if (win) {
    const chat = win.querySelector(".tg-chat"), lang = document.documentElement.lang || "en";
    const localize = (root) => {
      root.querySelectorAll(".tg-time").forEach((t) => {
        const dt = new Date(t.getAttribute("datetime"));
        if (!isNaN(dt)) t.textContent = dt.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
      });
      root.querySelectorAll(".tg-day time").forEach((t) => {
        const dt = new Date(t.getAttribute("datetime"));
        if (!isNaN(dt)) t.textContent = dt.toLocaleDateString(lang, { day: "numeric", month: "long" });
      });
    };
    const playIn = (root) => {
      if (!("IntersectionObserver" in window) || calm) return;
      const io = new IntersectionObserver((es) => es.forEach((e) => {
        const v = e.target;
        if (e.isIntersecting) { if (!v.src) v.src = v.dataset.src; v.play().catch(() => {}); } else { v.pause(); }
      }), { threshold: 0.35 });
      root.querySelectorAll("video[data-src]").forEach((v) => io.observe(v));
    };
    localize(chat);
    let sig = "", visible = false, busy = false;
    const refresh = () => {
      if (!visible || busy || document.hidden) return;
      busy = true;
      fetch(win.dataset.feed, { cache: "no-store" }).then((r) => r.json()).then((d) => {
        if (!d.html || d.sig === sig) return;
        const first = !sig; sig = d.sig;
        if (first) return;   // перший запит лише запам'ятовує стан
        const box = document.createElement("div"); box.innerHTML = d.html;
        const known = new Set([...chat.querySelectorAll(".tg-msg")].map((m) => m.dataset.id));
        const fresh = d.ids.some((id) => !known.has(String(id)));
        if (fresh) {   // нові пости: міняємо стрічку, нові випливають
          chat.innerHTML = d.html;
          chat.querySelectorAll(".tg-msg").forEach((m) => { if (!known.has(m.dataset.id)) m.classList.add("tg-new"); });
          localize(chat); playIn(chat);
        } else {       // ті самі пости: оновлюємо лише реакції й перегляди, відео не перезапускаємо
          box.querySelectorAll(".tg-msg").forEach((m) => {
            const cur = chat.querySelector(`.tg-msg[data-id="${m.dataset.id}"]`);
            if (!cur) return;
            ["tg-reacts", "tg-views"].forEach((c) => { const a = cur.querySelector("." + c), b = m.querySelector("." + c); if (a && b && a.innerHTML !== b.innerHTML) a.innerHTML = b.innerHTML; });
          });
        }
        const subs = win.querySelector(".tg-subs"); if (subs && d.subs) subs.textContent = d.subs;
      }).catch(() => {}).finally(() => { busy = false; });
    };
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((es) => { visible = es[0].isIntersecting; if (visible) refresh(); }).observe(win);
      setInterval(refresh, 60000);
    }
  }

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
