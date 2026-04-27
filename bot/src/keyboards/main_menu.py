from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class MainMenuKeyboard:
    @staticmethod
    def get_keyboard():
        """Основное меню"""
        keyboard = [
            [
                InlineKeyboardButton("💬 Новый диалог", callback_data="new_conversation"),
                InlineKeyboardButton("📋 Мои диалоги", callback_data="list_conversations")
            ],
            [
                InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
                InlineKeyboardButton("❓ Помощь", callback_data="help")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_quick_replies():
        """Быстрые ответы"""
        keyboard = [
            [
                InlineKeyboardButton("➡️ Продолжи", callback_data="quick_continue"),
                InlineKeyboardButton("📝 Поясни", callback_data="quick_explain")
            ],
            [
                InlineKeyboardButton("💡 Дай пример", callback_data="quick_example"),
                InlineKeyboardButton("❓ Что это?", callback_data="quick_what")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
