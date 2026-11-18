/* Заставка головної: раз за сесію і не для тих, хто вимкнув рух. Підключається синхронно в <head>, щоб клас стояв до першого кадру. */
(() => {
  const root = document.documentElement;
  try {
    if (sessionStorage.getItem("bmc_intro") || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    sessionStorage.setItem("bmc_intro", "1");
  } catch (e) { return; }
  root.classList.add("intro-on");
  document.addEventListener("DOMContentLoaded", () => {
    const tc = document.querySelector(".intro-tc");
    if (!tc) return;
    const t0 = performance.now();
    const tick = (now) => {
      const f = Math.floor((now - t0) * 24 / 1000);
      tc.textContent = `00:00:${String(Math.floor(f / 24)).padStart(2, "0")}:${String(f % 24).padStart(2, "0")}`;
      if (now - t0 < 1000) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
})();
