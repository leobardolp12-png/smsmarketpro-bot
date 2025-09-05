from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def start_kb():
    keyboard = [
        [InlineKeyboardButton("DEPOSITAR SALDO", callback_data="depositar_saldo")],
        [
            InlineKeyboardButton("SMS", callback_data="sms"),
            InlineKeyboardButton("INFO", callback_data="info")
        ],
        [InlineKeyboardButton("HISTORIAL", callback_data="historial")],
        [
            InlineKeyboardButton("PERFIL", callback_data="perfil"),
            InlineKeyboardButton("REFERIDOS", callback_data="referidos")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)