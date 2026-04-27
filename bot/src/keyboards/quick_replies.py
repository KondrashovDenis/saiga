from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class QuickRepliesKeyboard:
    @staticmethod
    def get_keyboard():
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
