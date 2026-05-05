// conversation.js — rename диалога + open/close модалов (delete, share).
// Заменяет inline onclick="..." и inline <script> в conversation.html для CSP-compliance.
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var csrfMeta = document.querySelector('meta[name=csrf-token]');
    var csrf = csrfMeta ? csrfMeta.content : '';

    // ── Rename ──
    var renameBtn = document.getElementById('renameBtn');
    var titleEl = document.getElementById('convTitle');
    if (renameBtn && titleEl) {
      renameBtn.addEventListener('click', async function () {
        var current = titleEl.textContent.trim();
        var next = prompt('Новое название диалога:', current);
        if (!next || next.trim() === '' || next.trim() === current) return;
        var id = titleEl.dataset.conversationId;
        try {
          var r = await fetch('/conversations/' + id + '/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ title: next.trim() }),
          });
          if (!r.ok) { alert('Ошибка: ' + r.status); return; }
          var d = await r.json();
          titleEl.textContent = d.title;
          document.title = d.title;
          var sb = document.querySelector('.sb-conv[href$="/conversations/' + id + '"] .sb-conv-title');
          if (sb) sb.textContent = d.title;
        } catch (e) { alert('Сетевая ошибка: ' + e.message); }
      });
    }

    // ── Modal open/close (event delegation по data-modal-* атрибутам) ──
    document.addEventListener('click', function (e) {
      var t = e.target;
      if (!(t instanceof Element)) return;
      var openId = t.getAttribute('data-modal-open');
      if (openId) {
        var m = document.getElementById(openId);
        if (m) m.classList.add('open');
        return;
      }
      var closeId = t.getAttribute('data-modal-close');
      if (closeId) {
        var m2 = document.getElementById(closeId);
        if (m2) m2.classList.remove('open');
      }
    });
  });
})();
