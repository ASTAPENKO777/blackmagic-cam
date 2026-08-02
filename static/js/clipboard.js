// Clipboard helper with synchronous fallback.
// Telegram's Android in-app browser often blocks navigator.clipboard, so without a
// fallback the Copy buttons silently fail and the user can't send USDT.
window.bmcCopy = function (text) {
  text = String(text == null ? '' : text);

  function fallback() {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:-9999px;left:0;opacity:0;pointer-events:none;';
    document.body.appendChild(ta);
    ta.select();
    try { ta.setSelectionRange(0, text.length); } catch (e) {}
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
    return ok;
  }

  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text).then(
      function () { return true; },
      function () { return fallback(); }
    );
  }
  return Promise.resolve(fallback());
};
