// Restore access link from localStorage, with a cookie fallback so Telegram
// WebView users who lost localStorage still see the saved-guide banner.
(function () {
  function readCookie(name) {
    var pairs = (document.cookie || '').split(';');
    for (var i = 0; i < pairs.length; i++) {
      var p = pairs[i].trim();
      if (p.indexOf(name + '=') === 0) {
        try { return decodeURIComponent(p.slice(name.length + 1)); } catch (e) { return ''; }
      }
    }
    return '';
  }

  var token = '';
  try { token = localStorage.getItem('bmc_access_token') || ''; } catch (e) {}
  var device = '';
  try { device = localStorage.getItem('bmc_device') || ''; } catch (e) {}

  if (!token) {
    token = readCookie('bmc_last');
    // Cookie-only users won't have a device slug; the banner will fall back
    // to the generic "your device" label.
  }
  if (!token) return;

  // If user is on landing or select page (any language), show a "restore access" banner
  var path = window.location.pathname;
  // Strip /ru or /ar prefix so RU/AR pages match the same check as English.
  var stripped = path.replace(/^\/(ru|ar)(?=\/|$)/, '') || '/';
  if (stripped === '/' || stripped === '/select') {
    var i18n = window.BMC_I18N || {};
    var restoreText = i18n.restore_bar_text || 'You have a saved guide — ';
    var restoreLinkTpl = i18n.restore_bar_link || 'View {device} settings →';

    var bar = document.createElement('div');
    bar.style.cssText = [
      'background: rgba(245,197,24,0.08)',
      'border-bottom: 1px solid rgba(245,197,24,0.2)',
      'padding: 10px 0',
      'text-align: center',
      'font-size: 0.82rem',
      'color: #888'
    ].join(';');

    var inner = document.createElement('div');
    inner.className = 'container';

    var text = document.createTextNode(restoreText);
    inner.appendChild(text);

    var link = document.createElement('a');
    link.href = '/access/' + encodeURIComponent(token);
    link.style.cssText = 'color: #f5c518; font-weight: 600;';

    var deviceText = device ? device.replace(/-/g, ' ') : 'your device';
    link.textContent = restoreLinkTpl.replace('{device}', deviceText);
    inner.appendChild(link);

    bar.appendChild(inner);

    var nav = document.querySelector('nav');
    if (nav && nav.parentNode) {
      nav.parentNode.insertBefore(bar, nav.nextSibling);
    }
  }
})();

// FAQ <details> — accordion behavior + smooth close animation
(function () {
  var items = Array.prototype.slice.call(document.querySelectorAll('details.faq-item'));

  function animateClose(details) {
    var body = details.querySelector('.faq-body');
    if (!body || details.dataset.closing === '1') return;
    if (!details.hasAttribute('open')) return;
    details.dataset.closing = '1';

    body.style.gridTemplateRows = '1fr';
    requestAnimationFrame(function () {
      body.style.gridTemplateRows = '0fr';
    });

    var done = function () {
      body.removeEventListener('transitionend', onEnd);
      details.removeAttribute('open');
      body.style.gridTemplateRows = '';
      delete details.dataset.closing;
    };
    var onEnd = function (ev) {
      if (ev.propertyName !== 'grid-template-rows') return;
      done();
    };
    body.addEventListener('transitionend', onEnd);
    setTimeout(done, 500);
  }

  items.forEach(function (details) {
    var summary = details.querySelector('summary');
    if (!summary) return;

    summary.addEventListener('click', function (e) {
      if (details.hasAttribute('open')) {
        // Closing the currently open item — animate it.
        e.preventDefault();
        animateClose(details);
        return;
      }
      // Opening: close every other open item first, then let the browser open this one.
      items.forEach(function (other) {
        if (other !== details && other.hasAttribute('open')) {
          animateClose(other);
        }
      });
    });
  });
})();

// Language switcher cinematic transition
(function () {
  var LANG_LABELS = {
    en: { code: 'EN', sub: 'ENGLISH' },
    ru: { code: 'RU', sub: 'РУССКИЙ' },
    ar: { code: 'AR', sub: 'العربية' }
  };

  var html = document.documentElement;
  var overlay = document.getElementById('lang-transition');

  // Outro: if pre-cover class was set on load, animate panels off-screen.
  if (html.classList.contains('lt-out') && overlay) {
    var code = html.dataset.ltCode;
    var sub = html.dataset.ltSub;
    var codeEl = overlay.querySelector('[data-lt-code]');
    var subEl = overlay.querySelector('[data-lt-sub]');
    if (codeEl && code) codeEl.textContent = code;
    if (subEl && sub) subEl.textContent = sub;

    var startOutro = function () {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          html.classList.add('lt-leaving');
          // OUT total ≈ 0.18s delay + 0.55s anim = 730ms; +70ms buffer.
          setTimeout(function () {
            html.classList.remove('lt-out', 'lt-leaving');
          }, 800);
        });
      });
    };
    if (document.readyState === 'complete') startOutro();
    else window.addEventListener('load', startOutro);
  }

  // Intro: hijack lang button clicks, animate cover, then navigate.
  var btns = document.querySelectorAll('.lang-btn');
  btns.forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      if (btn.classList.contains('lang-active')) {
        e.preventDefault();
        return;
      }
      // Modifier keys → let the browser handle (new tab etc.)
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button === 1) return;
      if (!overlay) return;

      e.preventDefault();
      var href = btn.getAttribute('href');
      var target = (btn.getAttribute('hreflang') || 'en').toLowerCase();
      var label = LANG_LABELS[target] || { code: target.toUpperCase(), sub: '' };

      var codeEl = overlay.querySelector('[data-lt-code]');
      var subEl = overlay.querySelector('[data-lt-sub]');
      if (codeEl) codeEl.textContent = label.code;
      if (subEl) subEl.textContent = label.sub;

      try {
        sessionStorage.setItem('bmc_lt', JSON.stringify({
          target: target,
          code: label.code,
          sub: label.sub
        }));
      } catch (err) {}

      html.classList.add('lt-in');
      // Hold ~280ms before navigating so the IN animation is clearly visible even when
      // the next page loads quickly. After this delay, navigation runs in parallel with
      // the rest of the IN — the new page already has the cover via the inline head
      // script, so there's no flash.
      setTimeout(function () {
        window.location.href = href;
      }, 280);
    });
  });
})();
