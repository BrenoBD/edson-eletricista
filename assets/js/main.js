/* =========================================================================
   EDSON ELETRICISTA — interações (autocontido, leve)
   ========================================================================= */
(function () {
  'use strict';
  function ready(fn) { if (document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }

  // Header mobile
  function initHeader() {
    var header = document.getElementById('site-header');
    var toggle = document.getElementById('nav-toggle');
    var nav = document.getElementById('site-nav');
    if (!header || !toggle) return;
    toggle.addEventListener('click', function () {
      var open = header.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    if (nav) nav.addEventListener('click', function (e) { if (e.target.closest('a')) header.classList.remove('open'); });
  }

  // FAQ acordeão
  function initFaq() {
    var items = document.querySelectorAll('.faq-item');
    if (!items.length) return;
    items.forEach(function (item) {
      var q = item.querySelector('.faq-q');
      var wrap = item.querySelector('.faq-a-wrap');
      q.addEventListener('click', function () {
        var open = item.classList.contains('active');
        items.forEach(function (o) { o.classList.remove('active'); o.querySelector('.faq-a-wrap').style.maxHeight = null; });
        if (!open) { item.classList.add('active'); wrap.style.maxHeight = wrap.scrollHeight + 'px'; }
      });
    });
  }

  ready(function () { initHeader(); initFaq(); });
})();
