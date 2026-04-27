/**
 * Основные функции для работы с чатом
 */

class ChatHandler {
    constructor(options) {
        this.conversationId = options.conversationId;
        this.messageContainer = document.getElementById(options.messageContainerId || 'chatMessages');
        this.messageForm = document.getElementById(options.messageFormId || 'messageForm');
        this.messageInput = document.getElementById(options.messageInputId || 'messageInput');
        this.typingIndicator = null;
        
        this.apiEndpoints = {
            messages: `/api/conversations/${this.conversationId}/messages`,
            generate: `/api/llm/generate`
        };
        
        this.init();
    }
    
    /**
     * Инициализация обработчиков событий
     */
    init() {
        this.scrollToBottom();
        
        if (this.messageForm) {
            this.messageForm.addEventListener('submit', this.handleSubmit.bind(this));
        }
        
        if (this.messageInput) {
            this.messageInput.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    e.stopPropagation();
                    this.handleSubmit(e);
                }
            });
        }
        
        this.initQuickReplies();
        this.initMessageReactions();
    }
    
    /**
     * Инициализация быстрых ответов
     */
    initQuickReplies() {
        const quickRepliesContainer = document.getElementById('quickReplies');
        if (quickRepliesContainer) {
            quickRepliesContainer.addEventListener('click', (e) => {
                if (e.target.classList.contains('quick-reply-btn')) {
                    const text = e.target.textContent;
                    this.messageInput.value = text;
                    this.messageInput.focus();
                }
            });
        }
    }
    
    /**
     * Инициализация реакций на сообщения
     */
    initMessageReactions() {
        this.messageContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('reaction-btn')) {
                e.target.classList.toggle('active');
                // Здесь можно добавить отправку реакции на сервер
            }
        });
    }
    
    /**
     * Обработка отправки сообщения
     */
    handleSubmit(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const message = this.messageInput.value.trim();
        if (!message) return;
        
        // Блокируем повторную отправку
        if (this.typingIndicator) {
            return;
        }
        
        this.addMessage('user', message);
        this.messageInput.value = '';
        this.showTypingIndicator();
        
        this.sendMessage(message)
            .then(() => this.generateResponse(message))
            .catch(error => {
                console.error('Error sending message:', error);
                this.hideTypingIndicator();
                this.showErrorMessage('Ошибка при отправке сообщения');
            });
    }
    
    /**
     * Отправка сообщения на сервер
     */
    sendMessage(message) {
        return fetch(this.apiEndpoints.messages, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content: message })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        });
    }
    
    /**
     * Запрос генерации ответа от LLM
     */
    generateResponse(message) {
        return fetch(this.apiEndpoints.generate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                conversation_id: this.conversationId,
                message: message
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            this.hideTypingIndicator();
            this.addMessage('assistant', data.message);
        })
        .catch(error => {
            console.error('Error generating response:', error);
            this.hideTypingIndicator();
            this.showErrorMessage('Ошибка при получении ответа от модели');
        });
    }
    
    /**
     * Добавление сообщения в чат
     */
    addMessage(role, content) {
        const messageElement = document.createElement('div');
        messageElement.className = `message message-${role} fade-in`;
        
        const timestamp = new Date().toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const avatarHtml = this.createAvatar(role);
        const reactionsHtml = role === 'assistant' ? this.createReactions() : '';
        const markdownContent = this.renderMarkdown(content);
        
        messageElement.innerHTML = `
            <div class="message-header">
                ${avatarHtml}
                <span class="message-timestamp">${timestamp}</span>
            </div>
            <div class="message-content">
                ${markdownContent}
            </div>
            ${reactionsHtml}
        `;
        
        this.messageContainer.appendChild(messageElement);
        this.scrollToBottom();
        
        if (role === 'assistant') {
            this.showQuickReplies();
        }
    }
    
    /**
     * Создание аватара
     */
    createAvatar(role) {
        const isUser = role === 'user';
        const initials = isUser ? 'Вы' : 'AI';
        const className = `message-avatar avatar-${role}`;
        
        return `<div class="${className}">${initials}</div>`;
    }
    
    /**
     * Создание реакций
     */
    createReactions() {
        const reactions = ['👍', '👎', '🤔', '❤️'];
        return `
            <div class="message-reactions">
                ${reactions.map(emoji => 
                    `<button class="reaction-btn" data-reaction="${emoji}">${emoji}</button>`
                ).join('')}
            </div>
        `;
    }
    
    /**
     * Простой рендеринг Markdown
     */
    renderMarkdown(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
    
    /**
     * Показать быстрые ответы
     */
    showQuickReplies() {
        const quickReplies = document.getElementById('quickReplies');
        if (quickReplies) {
            quickReplies.style.display = 'flex';
        }
    }
    
    /**
     * Создать и показать индикатор печати
     */
    showTypingIndicator() {
        // Удаляем предыдущий индикатор, если есть
        this.hideTypingIndicator();
        
        // Создаем новый индикатор печати
        this.typingIndicator = document.createElement('div');
        this.typingIndicator.className = 'message message-assistant typing-indicator fade-in';
        this.typingIndicator.innerHTML = `
            <div class="message-header">
                <div class="message-avatar avatar-assistant">AI</div>
                <span class="message-timestamp">печатает...</span>
            </div>
            <div class="message-content">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        this.messageContainer.appendChild(this.typingIndicator);
        this.scrollToBottom();
    }
    
    /**
     * Скрыть индикатор печати
     */
    hideTypingIndicator() {
        if (this.typingIndicator) {
            this.typingIndicator.remove();
            this.typingIndicator = null;
        }
    }
    
    /**
     * Показать сообщение об ошибке
     */
    showErrorMessage(errorText) {
        const errorElement = document.createElement('div');
        errorElement.className = 'alert alert-danger mt-3 fade-in';
        errorElement.textContent = errorText;
        
        this.messageContainer.appendChild(errorElement);
        this.scrollToBottom();
        
        setTimeout(() => {
            errorElement.remove();
        }, 5000);
    }
    
    /**
     * Прокрутка чата вниз
     */
    scrollToBottom() {
        if (this.messageContainer) {
            this.messageContainer.scrollTo({
                top: this.messageContainer.scrollHeight,
                behavior: 'smooth'
            });
        }
    }
}

/**
 * Управление темами
 */
class ThemeManager {
    constructor() {
        this.currentTheme = this.getStoredTheme() || this.getSystemTheme();
        this.init();
    }
    
    init() {
        this.applyTheme(this.currentTheme);
        this.initThemeToggle();
    }
    
    getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    
    getStoredTheme() {
        return localStorage.getItem('theme');
    }
    
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this.updateThemeToggle(theme);
        this.saveTheme(theme);
    }
    
    saveTheme(theme) {
        localStorage.setItem('theme', theme);
        
        // Отправляем на сервер для сохранения в профиле
        fetch('/settings/theme', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ theme: theme })
        }).catch(error => console.warn('Failed to save theme to server:', error));
    }
    
    toggleTheme() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.currentTheme = newTheme;
        this.applyTheme(newTheme);
    }
    
    updateThemeToggle(theme) {
        const toggle = document.getElementById('themeToggle');
        if (toggle) {
            const icon = toggle.querySelector('i');
            if (icon) {
                icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
            }
        }
    }
    
    initThemeToggle() {
        const toggle = document.getElementById('themeToggle');
        if (toggle) {
            toggle.addEventListener('click', () => this.toggleTheme());
        }
        
        // Слушаем изменения системной темы
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!this.getStoredTheme()) {
                this.currentTheme = e.matches ? 'dark' : 'light';
                this.applyTheme(this.currentTheme);
            }
        });
    }
}

/**
 * Обработчик общих действий для диалогов
 */
class ConversationManager {
    constructor(conversationId) {
        this.conversationId = conversationId;
        this.shareBtn = document.getElementById('shareBtn');
        this.copyBtn = document.getElementById('copyBtn');
        
        this.init();
    }
    
    init() {
        if (this.shareBtn) {
            this.shareBtn.addEventListener('click', this.handleShare.bind(this));
        }
        
        if (this.copyBtn) {
            this.copyBtn.addEventListener('click', this.handleCopy.bind(this));
        }
    }
    
    handleShare() {
        fetch(`/conversations/${this.conversationId}/share`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            document.getElementById('shareLink').value = data.shareUrl;
            const shareModal = new bootstrap.Modal(document.getElementById('shareModal'));
            shareModal.show();
        })
        .catch(error => {
            console.error('Error sharing conversation:', error);
            alert('Не удалось создать ссылку для шаринга.');
        });
    }
    
    handleCopy() {
        const shareLink = document.getElementById('shareLink');
        shareLink.select();
        navigator.clipboard.writeText(shareLink.value);
        
        const copySuccess = document.getElementById('copySuccess');
        copySuccess.classList.remove('d-none');
        
        setTimeout(() => {
            copySuccess.classList.add('d-none');
        }, 3000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем менеджер тем
    new ThemeManager();
    
    // Получаем ID диалога из элемента данных или из URL
    const conversationElement = document.querySelector('[data-conversation-id]');
    if (conversationElement) {
        const conversationId = conversationElement.dataset.conversationId;
        
        // Инициализируем обработчик чата
        const chatHandler = new ChatHandler({
            conversationId: conversationId,
            messageContainerId: 'chatMessages',
            messageFormId: 'messageForm',
            messageInputId: 'messageInput'
        });
        
        // Инициализируем менеджер диалогов
        const conversationManager = new ConversationManager(conversationId);
    }
});

// Обработка загрузки файлов
document.addEventListener('DOMContentLoaded', function() {
    const fileUploadBtn = document.getElementById('fileUploadBtn');
    const fileInput = document.getElementById('fileInput');
    
    if (fileUploadBtn && fileInput) {
        fileUploadBtn.addEventListener('click', function() {
            fileInput.click();
        });
        
        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
            }
        });
    }
});

function uploadFile(file) {
    const conversationId = document.querySelector('[data-conversation-id]').dataset.conversationId;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('conversation_id', conversationId);
    
    fetch('/api/files/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.extracted_text) {
            addMessage('user', `📄 ${file.name}:\n\n${data.extracted_text}`);
            generateResponseFromFile(data.extracted_text, file.name);
        } else {
            showErrorMessage(data.error || 'Ошибка обработки файла');
        }
    })
    .catch(error => {
        console.error('Ошибка загрузки файла:', error);
        showErrorMessage('Ошибка загрузки файла');
    });
}

function generateResponseFromFile(text, filename) {
    const conversationId = document.querySelector('[data-conversation-id]').dataset.conversationId;
    const prompt = `Проанализируй содержимое файла "${filename}":\n\n${text}`;
    
    showTypingIndicator();
    
    fetch('/api/llm/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            conversation_id: conversationId,
            message: prompt
        })
    })
    .then(response => response.json())
    .then(data => {
        hideTypingIndicator();
        addMessage('assistant', data.message);
    })
    .catch(error => {
        console.error('Ошибка генерации ответа:', error);
        hideTypingIndicator();
        showErrorMessage('Ошибка получения ответа от модели');
    });
}

function showErrorMessage(message) {
    const errorElement = document.createElement('div');
    errorElement.className = 'alert alert-danger mt-3 fade-in';
    errorElement.textContent = message;
    
    const messageContainer = document.getElementById('chatMessages');
    if (messageContainer) {
        messageContainer.appendChild(errorElement);
        messageContainer.scrollTo({
            top: messageContainer.scrollHeight,
            behavior: 'smooth'
        });
    }
    
    setTimeout(() => {
        if (errorElement.parentNode) {
            errorElement.remove();
        }
    }, 5000);
}

function addMessage(role, content) {
    const messageContainer = document.getElementById('chatMessages');
    if (!messageContainer) return;
    
    const messageElement = document.createElement('div');
    messageElement.className = `message message-${role} fade-in`;
    
    const timestamp = new Date().toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    const avatarText = role === 'user' ? 'Вы' : 'AI';
    
    messageElement.innerHTML = `
        <div class="message-header">
            <div class="message-avatar avatar-${role}">${avatarText}</div>
            <span class="message-timestamp">${timestamp}</span>
        </div>
        <div class="message-content">
            ${content.replace(/\n/g, '<br>')}
        </div>
    `;
    
    messageContainer.appendChild(messageElement);
    messageContainer.scrollTo({
        top: messageContainer.scrollHeight,
        behavior: 'smooth'
    });
}

function showTypingIndicator() {
    const messageContainer = document.getElementById('chatMessages');
    if (!messageContainer) return;
    
    const typingElement = document.createElement('div');
    typingElement.id = 'typingIndicator';
    typingElement.className = 'message message-assistant typing-indicator fade-in';
    typingElement.innerHTML = `
        <div class="message-header">
            <div class="message-avatar avatar-assistant">AI</div>
            <span class="message-timestamp">печатает...</span>
        </div>
        <div class="message-content">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    messageContainer.appendChild(typingElement);
    messageContainer.scrollTo({
        top: messageContainer.scrollHeight,
        behavior: 'smooth'
    });
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}
