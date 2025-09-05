from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

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

# Estados para ConversationHandler
DEPOSIT_AMOUNT, DEPOSIT_CONFIRM = range(2)

async def deposit_callback(update: Update, context: CallbackContext):
    """Inicia el flujo de depósito"""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("💰 ¿Cuánto deseas cargar? (ej. 100)")
    return DEPOSIT_AMOUNT

async def deposit_amount(update: Update, context: CallbackContext):
    """Recibe la cantidad de depósito"""
    text = update.message.text
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Por favor, ingresa un número válido mayor a 0.")
        return DEPOSIT_AMOUNT

    context.user_data["deposit_amount"] = amount
    # Mostrar datos bancarios de ejemplo y botones Confirmar/Cancelar
    keyboard = [
        [InlineKeyboardButton("Confirmar depósito", callback_data="confirm_deposit")],
        [InlineKeyboardButton("Cancelar", callback_data="cancel_deposit")]
    ]
    await update.message.reply_text(
        f"Envía la cantidad de ${amount:.2f} a nuestra cuenta bancaria:\n\n"
        "Banco: XXXX\nCuenta: 12345678\nCLABE: 012345678901234567\n\n"
        "Cuando hayas hecho el depósito, confirma abajo.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DEPOSIT_CONFIRM

async def confirm_deposit_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    amount = context.user_data.get("deposit_amount", 0)
    await query.message.reply_text(
        f"Perfecto ✅, ahora envía el comprobante de depósito como imagen o archivo. Monto: ${amount:.2f}"
    )
    return ConversationHandler.END  # seguiremos flujo para subir comprobante luego

async def cancel_deposit_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END