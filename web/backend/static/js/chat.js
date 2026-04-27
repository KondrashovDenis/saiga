// chat.js — markdown с правильно вложенными списками (nested внутри <li>).

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

  const scrollDown = () => { if (stream) stream.scrollTop = stream.scrollHeight; };

  // ───── Markdown render ─────
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

  function lineMeta(line) {
    const m = line.match(/^( *)(.*)$/);
    const indent = m[1].length;
    const t = m[2].trim();
    if (!t) return { kind: 'empty', indent };
    if (/^CODE\d+$/.test(t)) return { kind: 'code', indent, raw: t };
    if (/^#{1,4}\s+/.test(t)) return { kind: 'h', indent, raw: t };
    if (/^\d+\.\s+/.test(t)) return { kind: 'ol', indent, raw: t };
    if (/^[-*+]\s+/.test(t)) return { kind: 'ul', indent, raw: t };
    return { kind: 'p', indent, raw: t };
  }

  function renderMarkdown(src) {
    // 1) fenced code blocks
    const blocks = [];
    let txt = src.replace(/```(\w+)?\n?([\s\S]*?)```/g, (_, lang, code) => {
      blocks.push(`<pre><code>${escapeHtml(code.replace(/\n+$/, ''))}</code></pre>`);
      return `CODE${blocks.length - 1}`;
    });
    txt = escapeHtml(txt);

    const lines = txt.split('\n');
    const out = [];
    let para = [];
    // stack: [{ tag: 'ol'|'ul', indent, liOpen: bool }]
    const stack = [];

    const flushPara = () => {
      if (para.length) {
        out.push('<p>' + renderInline(para.join(' ')) + '</p>');
        para = [];
      }
    };
    const closeOpenLi = () => {
      const top = stack[stack.length - 1];
      if (top && top.liOpen) { out.push('</li>'); top.liOpen = false; }
    };
    const closeListsTo = (indent, kind) => {
      // закрываем стек пока top.indent > indent ИЛИ (top.indent==indent && top.tag != kind)
      while (stack.length) {
        const top = stack[stack.length - 1];
        if (top.indent > indent || (top.indent === indent && top.tag !== kind)) {
          if (top.liOpen) { out.push('</li>'); top.liOpen = false; }
          out.push(`</${top.tag}>`);
          stack.pop();
        } else break;
      }
    };
    const closeAll = () => {
      while (stack.length) {
        const top = stack.pop();
        if (top.liOpen) out.push('</li>');
        out.push(`</${top.tag}>`);
      }
    };

    for (const line of lines) {
      const meta = lineMeta(line);

      if (meta.kind === 'code') {
        flushPara(); closeAll();
        out.push(blocks[+meta.raw.slice(4)]);
        continue;
      }
      if (meta.kind === 'h') {
        flushPara(); closeAll();
        const h = meta.raw.match(/^(#{1,4})\s+(.+?)\s*#*$/);
        const lvl = h[1].length;
        out.push(`<h${lvl}>${renderInline(h[2])}</h${lvl}>`);
        continue;
      }
      if (meta.kind === 'ol' || meta.kind === 'ul') {
        flushPara();
        const tag = meta.kind;

        // 1) закрыть все более глубокие списки и не-нашего типа на том же уровне
        closeListsTo(meta.indent, tag);

        const top = stack[stack.length - 1];
        if (!top || top.indent < meta.indent) {
          // OPEN nested list внутри текущего открытого <li> (если есть)
          out.push(`<${tag}>`);
          stack.push({ tag, indent: meta.indent, liOpen: false });
        } else {
          // тот же список — закрываем предыдущий <li>
          closeOpenLi();
        }
        const m = meta.raw.match(/^(?:\d+\.|[-*+])\s+(.+)/);
        out.push(`<li>${renderInline(m[1])}`);
        stack[stack.length - 1].liOpen = true;
        continue;
      }
      if (meta.kind === 'empty') {
        flushPara();
        // не закрываем списки на пустой строке — между li часто пустые строки
        continue;
      }
      // обычная строка (параграф)
      // Если мы внутри <li> (top.liOpen) и indent > top.indent — это продолжение li-текста.
      const top = stack[stack.length - 1];
      if (top && top.liOpen && meta.indent > top.indent) {
        // дополняем текст внутри открытого li
        const lastIdx = out.length - 1;
        if (lastIdx >= 0) out[lastIdx] += ' ' + renderInline(meta.raw);
        continue;
      }
      // Иначе — закрываем все списки и параграф
      closeAll();
      para.push(line);
    }
    flushPara(); closeAll();
    return out.join('\n');
  }

  // отрендерить в исторических .msg-content
  document.querySelectorAll('.msg-content').forEach((el) => {
    if (el.dataset.rendered) return;
    el.innerHTML = renderMarkdown(el.textContent);
    el.dataset.rendered = '1';
  });
  scrollDown();

  const now = () => new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

  function appendMessage(role, content) {
    const el = document.createElement('div');
    el.className = 'msg';
    el.dataset.role = role;
    const initial = role === 'user' ? userInitial : 'S';
    const roleLabel = role === 'user' ? 'Вы' : 'Saiga';
    el.innerHTML = `
      <div class="msg-avatar ${role}">${escapeHtml(initial)}</div>
      <div class="msg-body">
        <div class="msg-role">${roleLabel} · ${now()}</div>
        <div class="msg-content" data-rendered="1">${renderMarkdown(content)}</div>
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
        <div class="msg-content"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
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

  let busy = false;
  async function send(text) {
    if (busy || !text.trim()) return;
    busy = true;
    if (sendBtn) sendBtn.disabled = true;

    appendMessage('user', text);
    input.value = '';
    input.style.height = 'auto';
    appendTyping();

    try {
      const r1 = await fetch(`/api/conversations/${conversationId}/messages`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text })
      });
      if (!r1.ok) throw new Error('Не удалось сохранить сообщение');
      const r2 = await fetch('/api/llm/generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, message: text })
      });
      const data = await r2.json();
      removeTyping();
      if (!r2.ok) showError(data.error || 'Ошибка генерации');
      else appendMessage('assistant', data.message);
    } catch (e) {
      removeTyping();
      showError('Сеть: ' + e.message);
    } finally {
      busy = false;
      if (sendBtn) sendBtn.disabled = false;
      input.focus();
    }
  }

  if (form) form.addEventListener('submit', (e) => { e.preventDefault(); send(input.value); });

  if (quickReplies) {
    quickReplies.addEventListener('click', (e) => {
      if (e.target.classList.contains('qr-btn')) {
        input.value = e.target.textContent;
        input.focus();
      }
    });
  }

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
        if (data.extracted_text) await send(`📄 ${file.name}:\n\n${data.extracted_text}`);
        else showError(data.error || 'Не удалось обработать файл');
      } catch (err) { showError('Загрузка файла: ' + err.message); }
      fileInput.value = '';
    });
  }

  if (shareBtn) {
    shareBtn.addEventListener('click', async () => {
      try {
        const r = await fetch(`/conversations/${conversationId}/share`, { method: 'POST' });
        const data = await r.json();
        document.getElementById('shareLink').value = data.shareUrl;
        document.getElementById('shareModal').classList.add('open');
      } catch (e) { showError('Не удалось создать ссылку для шаринга'); }
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

  document.querySelectorAll('.modal-back').forEach((m) => {
    m.addEventListener('click', (e) => { if (e.target === m) m.classList.remove('open'); });
  });
})();
