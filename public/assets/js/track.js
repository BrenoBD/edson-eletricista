/* =========================================================================
   Rastreamento leve — visita + clique no botão de contato.
   Envia eventos para /track (mesmo domínio) via sendBeacon (robusto mesmo
   quando a pessoa sai da página rumo ao WhatsApp). Sem cookies, sem libs.
   ========================================================================= */
(function () {
  'use strict';
  var page = location.pathname;

  function send(data) {
    try {
      data.page = page;
      var body = JSON.stringify(data);
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/track', new Blob([body], { type: 'application/json' }));
      } else {
        fetch('/track', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body, keepalive: true });
      }
    } catch (e) { /* silêncio */ }
  }

  // visita (pageview)
  send({ type: 'view' });

  // clique no botão de contato (WhatsApp ou telefone)
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var channel = href.indexOf('wa.me') > -1 ? 'whatsapp'
                : (href.indexOf('tel:') === 0 ? 'phone' : null);
    if (!channel) return;
    send({ type: 'contact', channel: channel });
  }, true);
})();
