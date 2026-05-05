// auth-login.js — Telegram deep-link login flow на странице /auth/login.
// Endpoint /api/telegram/login/start — anonymous, exempt от CSRF (см. web/backend/app.py).
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('tg-login-btn');
    var statusEl = document.getElementById('tg-login-status');
    if (!btn || !statusEl) return;

    var pollTimer = null;

    async function startLogin() {
      btn.disabled = true;
      statusEl.textContent = '...';
      try {
        var r = await fetch('/api/telegram/login/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        if (!r.ok) {
          statusEl.textContent = 'Не удалось начать вход. Попробуй ещё раз.';
          btn.disabled = false;
          return;
        }
        var data = await r.json();
        window.open(data.url, '_blank', 'noopener');
        statusEl.innerHTML = 'Открой Telegram и нажми <b>Start</b>. Ждём подтверждения...';
        pollStatus(data.token);
      } catch (e) {
        statusEl.textContent = 'Сетевая ошибка: ' + e.message;
        btn.disabled = false;
      }
    }

    function pollStatus(token) {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(async function () {
        try {
          var r = await fetch('/api/telegram/login/status?token=' + encodeURIComponent(token));
          if (r.status === 410) {
            clearInterval(pollTimer);
            statusEl.textContent = '⏰ Истекло время ожидания. Жми кнопку снова.';
            btn.disabled = false;
            return;
          }
          var d = await r.json();
          if (d.status === 'ok') {
            clearInterval(pollTimer);
            statusEl.textContent = '✅ Вход выполнен, переходим...';
            window.location = d.redirect || '/';
          }
        } catch (e) { /* network blip — try again */ }
      }, 2000);

      // Стоп через 10 минут (TTL токена).
      setTimeout(function () {
        if (pollTimer) {
          clearInterval(pollTimer);
          if (statusEl.textContent.indexOf('✅') === -1) {
            statusEl.textContent = '⏰ Истекло. Жми кнопку снова.';
            btn.disabled = false;
          }
        }
      }, 10 * 60 * 1000);
    }

    btn.addEventListener('click', startLogin);
  });
})();
