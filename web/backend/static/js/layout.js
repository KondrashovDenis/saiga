// layout.js — user menu (бургер аккаунта), мобильный sidebar toggle, закрытие flash-сообщений.
// Загружается на каждой странице из layout.html.
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    // ── User menu ──
    var userToggle = document.getElementById('userMenuToggle');
    var userMenu = document.getElementById('userMenu');
    if (userToggle && userMenu) {
      userToggle.addEventListener('click', function (e) {
        e.stopPropagation();
        userMenu.classList.toggle('open');
      });
      document.addEventListener('click', function () { userMenu.classList.remove('open'); });
      userMenu.addEventListener('click', function (e) { e.stopPropagation(); });
    }

    // ── Mobile sidebar toggle ──
    var menuToggle = document.getElementById('menuToggle');
    var sidebar = document.getElementById('sidebar');
    if (menuToggle && sidebar) {
      menuToggle.addEventListener('click', function () { sidebar.classList.toggle('open'); });
    }

    // ── Flash close (event delegation, чтобы покрывать flash-сообщения добавленные позже) ──
    document.addEventListener('click', function (e) {
      var t = e.target;
      if (t && t.classList && t.classList.contains('flash-close')) {
        var flash = t.closest('.flash');
        if (flash) flash.remove();
      }
    });
  });
})();
