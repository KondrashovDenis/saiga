// admin-users.js — confirmation prompt для delete-форм на /admin/users.
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[data-confirm-delete]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        var expected = form.dataset.confirmDelete;
        var typed = prompt('Удалить юзера ' + expected + ' со всеми диалогами?\n' +
                           'Введи точный username/email чтобы подтвердить:');
        if (typed !== expected) {
          e.preventDefault();
          if (typed !== null) alert('Не совпало. Удаление отменено.');
          return false;
        }
        // Кладём введённое значение в hidden input — backend проверит ещё раз.
        var hidden = form.querySelector('input[name=confirm]');
        if (hidden) hidden.value = typed;
      });
    });
  });
})();
