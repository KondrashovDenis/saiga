// chat.js — редизайн под новый layout (.msg, .msg-content, .modal-back и т.д.)
// + минимальный, безопасный markdown-рендер (без сторонних либ).

(function () {
  // ───── DOM ─────
  const stream = document.getElementById('chatStream');
  const messages = document.getElementById('chatMessages');
  const form = document.getElementById('messageForm');
  const input = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const quickReplies = document.getElementById('quickReplies');
  const fileBtn = document.getElementById('fileUploadBtn');
  const fileInput = document.getElementById('fileInput');
  const shareBtn = document.getElementById('shareBtn');
  const copyBtn = document.getElementById('copyBtn');

  if (!messages) return;

  const conversationId = messages.dataset.conversationId;
  const userInitial = (function () {
    const a = document.querySelector('.sb-avatar');
    return a ? a.textContent.trim() : 'U';
  })();

  // ───── Авторазмер textarea ─────
  if (input) {
    const autosize = () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    };
    input.addEventListener('input', autosize);
    autosize();

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
      }
    });
  }

  // ───── Скролл ─────
  const scrollDown = () => {
    if (stream) stream.scrollTop = stream.scrollHeight;
  };

  // ───── Markdown (свой, безопасный) ─────
  const escapeHtml = (s) => s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  function renderInline(s) {
    s = s.replace(/`([^`\n]+)`/g, (_, c) => `<code>${escapeHtml(c)}</code>`);
    s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
    s = s.replace(/(^|\W)_([^_\n]+)_(?!\w)/g, '$1<em>$2</em>');
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) =>
      `<a href="${escapeHtml(u)}" target="_blank" rel="noopener">${t}</a>`);
    return s;
  }

  // классификация строки → 'h' | 'ol' | 'ul' | 'code' | 'empty' | 'p'
  function lineKind(line) {
    const t = line.trim();
    if (!t) return 'empty';
    if (/^CODE\d+$/.test(t)) return 'code';
    if (/^#{1,4}\s+/.test(t)) return 'h';
    if (/^\d+\.\s+/.test(t)) return 'ol';
    if (/^[-*]\s+/.test(t)) return 'ul';
    return 'p';
  }

  function renderMarkdown(src) {
    // 1) выделить fenced code blocks
    const blocks = [];
    let txt = src.replace(/```(\w+)?\n?([\s\S]*?)```/g, (_, lang, code) => {
      blocks.push(`<pre><code>${escapeHtml(code.replace(/\n+$/, ''))}</code></pre>`);
      return `CODE${blocks.length - 1}`;
    });

    txt = escapeHtml(txt);
    let lines = txt.split('\n');

    // 2) схлопнуть пустые строки МЕЖДУ list-item'ами одного типа
    //    (Saiga часто отдаёт `- a\n\n- b\n\n- c` — это один список без зазоров)
    const cleaned = [];
    for (let i = 0; i < lines.length; i++) {
      if (lineKind(lines[i]) === 'empty') {
        // ищем ближайшую непустую строку вперёд и назад
        let prev = cleaned.length ? cleaned[cleaned.length - 1] : '';
        let next = '';
        for (let j = i + 1; j < lines.length; j++) {
          if (lineKind(lines[j]) !== 'empty') { next = lines[j]; break; }
        }
        const pk = lineKind(prev), nk = lineKind(next);
        if ((pk === 'ul' && nk === 'ul') || (pk === 'ol' && nk === 'ol')) {
          continue; // выкидываем пустую строку внутри списка
        }
      }
      cleaned.push(lines[i]);
    }
    lines = cleaned;

    // 3) построчный парсер
    const out = [];
    let inUL = false, inOL = false;
    let para = [];

    const flushPara = () => {
      if (para.length) {
        out.push('<p>' + renderInline(para.join(' ')) + '</p>');
        para = [];
      }
    };
    const closeLists = () => {
      if (inUL) { out.push('</ul>'); inUL = false; }
      if (inOL) { out.push('</ol>'); inOL = false; }
    };

    for (const line of lines) {
      const trimmed = line.trim();
      const kind = lineKind(line);

      if (kind === 'code') {
        flushPara(); closeLists();
        out.push(blocks[+trimmed.slice(4)]);
        continue;
      }
      if (kind === 'h') {
        flushPara(); closeLists();
        const h = trimmed.match(/^(#{1,4})\s+(.+?)\s*#*$/);
        const lvl = h[1].length;
        out.push(`<h${lvl}>${renderInline(h[2])}</h${lvl}>`);
        continue;
      }
      if (kind === 'ol') {
        flushPara();
        if (inUL) { out.push('</ul>'); inUL = false; }
        if (!inOL) { out.push('<ol>'); inOL = true; }
        const m = trimmed.match(/^\d+\.\s+(.+)/);
        out.push(`<li>${renderInline(m[1])}</li>`);
        continue;
      }
      if (kind === 'ul') {
        flushPara();
        if (inOL) { out.push('</ol>'); inOL = false; }
        if (!inUL) { out.push('<ul>'); inUL = true; }
        const m = trimmed.match(/^[-*]\s+(.+)/);
        out.push(`<li>${renderInline(m[1])}</li>`);
        continue;
      }
      if (kind === 'empty') {
        flushPara(); closeLists();
        continue;
      }
      // обычная строка
      closeLists();
      para.push(line);
    }
    flushPara(); closeLists();

    return out.join('\n');
  }

  // отрендерить markdown в существующих исторических .msg-content
  document.querySelectorAll('.msg-content').forEach((el) => {
    if (el.dataset.rendered) return;
    const raw = el.textContent;
    el.innerHTML = renderMarkdown(raw);
    el.dataset.rendered = '1';
  });
  scrollDown();

  const now = () => {
    const d = new Date();
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  };

  // ───── Добавить сообщение ─────
  function appendMessage(role, content) {
    const el = document.createElement('div');
    el.className = 'msg';
    el.dataset.role = role;
    const initial = role === 'user' ? userInitial : 'S';
    const roleLabel = role === 'user' ? 'Вы' : 'Saiga';
    const contentHtml = renderMarkdown(content);
    el.innerHTML = `
      <div class="msg-avatar ${role}">${escapeHtml(initial)}</div>
      <div class="msg-body">
        <div class="msg-role">${roleLabel} · ${now()}</div>
        <div class="msg-content" data-rendered="1">${contentHtml}</div>
      </div>`;
    messages.appendChild(el);
    scrollDown();
  }

  function appendTyping() {
    const el = document.createElement('div');
    el.className = 'msg msg-typing';
    el.id = 'typingMsg';
    el.innerHTML = `
      <div class="msg-avatar assistant">S</div>
      <div class="msg-body">
        <div class="msg-role">Saiga · печатает</div>
        <div class="msg-content">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>
      </div>`;
    messages.appendChild(el);
    scrollDown();
  }

  function removeTyping() {
    const el = document.getElementById('typingMsg');
    if (el) el.remove();
  }

  function showError(text) {
    const el = document.createElement('div');
    el.className = 'msg';
    el.style.color = 'var(--danger)';
    el.innerHTML = `<div class="msg-avatar" style="background:var(--danger); color:#fff;">!</div>
                    <div class="msg-body"><div class="msg-content">${escapeHtml(text)}</div></div>`;
    messages.appendChild(el);
    scrollDown();
    setTimeout(() => el.remove(), 8000);
  }

  // ───── Send ─────
  let busy = false;
  async function send(text) {
    if (busy) return;
    if (!text.trim()) return;
    busy = true;
    if (sendBtn) sendBtn.disabled = true;

    appendMessage('user', text);
    input.value = '';
    input.style.height = 'auto';
    appendTyping();

    try {
      const r1 = await fetch(`/api/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text })
      });
      if (!r1.ok) throw new Error('Не удалось сохранить сообщение');

      const r2 = await fetch('/api/llm/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, message: text })
      });
      const data = await r2.json();
      removeTyping();
      if (!r2.ok) {
        showError(data.error || 'Ошибка генерации');
      } else {
        appendMessage('assistant', data.message);
      }
    } catch (e) {
      removeTyping();
      showError('Сеть: ' + e.message);
    } finally {
      busy = false;
      if (sendBtn) sendBtn.disabled = false;
      input.focus();
    }
  }

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      send(input.value);
    });
  }

  // ───── Quick replies ─────
  if (quickReplies) {
    quickReplies.addEventListener('click', (e) => {
      if (e.target.classList.contains('qr-btn')) {
        input.value = e.target.textContent;
        input.focus();
      }
    });
  }

  // ───── File upload ─────
  if (fileBtn && fileInput) {
    fileBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      fd.append('conversation_id', conversationId);
      try {
        const r = await fetch('/api/files/upload', { method: 'POST', body: fd });
        const data = await r.json();
        if (data.extracted_text) {
          await send(`📄 ${file.name}:\n\n${data.extracted_text}`);
        } else {
          showError(data.error || 'Не удалось обработать файл');
        }
      } catch (err) {
        showError('Загрузка файла: ' + err.message);
      }
      fileInput.value = '';
    });
  }

  // ───── Share ─────
  if (shareBtn) {
    shareBtn.addEventListener('click', async () => {
      try {
        const r = await fetch(`/conversations/${conversationId}/share`, { method: 'POST' });
        const data = await r.json();
        document.getElementById('shareLink').value = data.shareUrl;
        document.getElementById('shareModal').classList.add('open');
      } catch (e) {
        showError('Не удалось создать ссылку для шаринга');
      }
    });
  }
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const link = document.getElementById('shareLink');
      link.select();
      navigator.clipboard.writeText(link.value);
      copyBtn.textContent = 'Скопировано ✓';
      setTimeout(() => (copyBtn.textContent = 'Скопировать'), 2000);
    });
  }

  // ───── Close modals on outside click ─────
  document.querySelectorAll('.modal-back').forEach((m) => {
    m.addEventListener('click', (e) => {
      if (e.target === m) m.classList.remove('open');
    });
  });
})();
