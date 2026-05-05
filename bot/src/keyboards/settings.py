from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class SettingsKeyboard:
    @staticmethod
    def get_keyboard():
        """Клавиатура настроек"""
        keyboard = [
            [
                InlineKeyboardButton("🌡️ Temperature", callback_data="set_temperature"),
                InlineKeyboardButton("🎯 Top P", callback_data="set_top_p")
            ],
            [
                InlineKeyboardButton("📊 Max Tokens", callback_data="set_max_tokens"),
                InlineKeyboardButton("🔔 Уведомления", callback_data="toggle_notifications")
            ],
            [
                InlineKeyboardButton("🌐 Открыть в Web", callback_data="web_login_request"),
            ],
            [
                InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
