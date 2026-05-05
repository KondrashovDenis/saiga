// settings.js — Telegram link / unlink на странице /settings.
// CSRF-токен берём из <meta name="csrf-token"> (общий для всех аутентифицированных страниц).
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var linkBtn = document.getElementById('tg-link-btn');
    var unlinkBtn = document.getElementById('tg-unlink-btn');
    var statusEl = document.getElementById('tg-status');
    if (!statusEl) return;
    var csrfMeta = document.querySelector('meta[name=csrf-token]');
    var csrf = csrfMeta ? csrfMeta.content : '';
    var pollTimer = null;

    async function startLink() {
      linkBtn.disabled = true;
      statusEl.textContent = '...';
      try {
        var r = await fetch('/api/telegram/link/start', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf },
        });
        if (r.status === 409) {
          statusEl.textContent = 'Уже привязан. Перезагрузи страницу.';
          return;
        }
        if (!r.ok) {
          statusEl.textContent = 'Ошибка запроса.';
          linkBtn.disabled = false;
          return;
        }
        var data = await r.json();
        window.open(data.url, '_blank', 'noopener');
        statusEl.innerHTML = 'Открой Telegram, нажми <b>Start</b>. Ждём подтверждения...';
        startPolling();
      } catch (e) {
        statusEl.textContent = 'Сетевая ошибка: ' + e.message;
        linkBtn.disabled = false;
      }
    }

    function startPolling() {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(async function () {
        try {
          var r = await fetch('/api/telegram/link/status');
          if (!r.ok) return;
          var d = await r.json();
          if (d.linked) {
            clearInterval(pollTimer);
            statusEl.textContent = '✅ Привязка выполнена, обновляем...';
            setTimeout(function () { window.location.reload(); }, 800);
          }
        } catch (e) { /* retry */ }
      }, 2000);
      setTimeout(function () {
        if (pollTimer) {
          clearInterval(pollTimer);
          if (statusEl.textContent.indexOf('✅') === -1) {
            statusEl.textContent = '⏰ Истекло. Жми кнопку снова.';
            if (linkBtn) linkBtn.disabled = false;
          }
        }
      }, 10 * 60 * 1000);
    }

    async function unlink() {
      if (!confirm('Отвязать Telegram-аккаунт?')) return;
      unlinkBtn.disabled = true;
      try {
        var r = await fetch('/api/telegram/unlink', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf },
        });
        if (!r.ok) {
          var d = await r.json().catch(function () { return {}; });
          statusEl.textContent = d.message || 'Ошибка отвязывания.';
          unlinkBtn.disabled = false;
          return;
        }
        statusEl.textContent = '✅ Отвязан. Обновляем...';
        setTimeout(function () { window.location.reload(); }, 600);
      } catch (e) {
        statusEl.textContent = 'Сетевая ошибка: ' + e.message;
        unlinkBtn.disabled = false;
      }
    }

    if (linkBtn) linkBtn.addEventListener('click', startLink);
    if (unlinkBtn) unlinkBtn.addEventListener('click', unlink);

    // ── Email-привязка (для TG-only юзеров) ──
    var emailLinkBtn = document.getElementById('email-link-btn');
    var emailLinkForm = document.getElementById('email-link-form');
    var elSubmit = document.getElementById('el-submit');
    var elStatus = document.getElementById('el-status');

    if (emailLinkBtn && emailLinkForm) {
      emailLinkBtn.addEventListener('click', function () {
        emailLinkForm.style.display = 'block';
        emailLinkBtn.style.display = 'none';
      });
    }

    async function submitEmailLink() {
      var email = (document.getElementById('el-email').value || '').trim();
      var pwd = document.getElementById('el-pwd').value || '';
      var pwd2 = document.getElementById('el-pwd2').value || '';
      if (!email || !email.includes('@')) {
        elStatus.textContent = 'Введи валидный email.';
        return;
      }
      if (pwd.length < 8) {
        elStatus.textContent = 'Пароль минимум 8 символов.';
        return;
      }
      if (pwd !== pwd2) {
        elStatus.textContent = 'Пароли не совпадают.';
        return;
      }
      elSubmit.disabled = true;
      elStatus.textContent = 'Отправляю...';
      var fd = new FormData();
      fd.append('email', email);
      fd.append('password', pwd);
      fd.append('password2', pwd2);
      fd.append('csrf_token', csrf);
      try {
        var r = await fetch('/auth/link-email', { method: 'POST', body: fd });
        var d = await r.json().catch(function () { return {}; });
        if (!r.ok) {
          elStatus.textContent = d.message || ('Ошибка ' + r.status);
          elSubmit.disabled = false;
          return;
        }
        elStatus.textContent = '✅ ' + (d.message || 'Привязан, обновляем...');
        setTimeout(function () { window.location.reload(); }, 1200);
      } catch (e) {
        elStatus.textContent = 'Сетевая ошибка: ' + e.message;
        elSubmit.disabled = false;
      }
    }

    if (elSubmit) elSubmit.addEventListener('click', submitEmailLink);
  });
})();
