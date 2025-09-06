from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

# Teclado principal
def start_kb():
    keyboard = [
        [InlineKeyboardButton("DEPOSITAR SALDO", callback_data="deposit")],
        [InlineKeyboardButton("SMS", callback_data="sms"), InlineKeyboardButton("INFO", callback_data="info")],
        [InlineKeyboardButton("HISTORIAL", callback_data="historial")],
        [InlineKeyboardButton("PERFIL", callback_data="perfil"), InlineKeyboardButton("REFERIDOS", callback_data="referidos")]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"👋 ¡Hola @{user.username or user.first_name}! Bienvenido a SMSProMarketBot 🚀\n\n💰 Tu saldo: $0\n\n¿Qué deseas hacer?",
        reply_markup=start_kb()
    )

# Estados de depósito
DEPOSIT_AMOUNT, DEPOSIT_CONFIRM = range(2)

async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("💰 ¿Cuánto deseas cargar? (ej. 100)")
    return DEPOSIT_AMOUNT

async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Ingresa un número válido mayor a 0.")
        return DEPOSIT_AMOUNT

    context.user_data["deposit_amount"] = amount
    kb = [[InlineKeyboardButton("Confirmar depósito", callback_data="confirm_deposit")],
          [InlineKeyboardButton("Cancelar", callback_data="cancel_deposit")]]
    await update.message.reply_text(
        f"Envía ${amount:.2f} a nuestra cuenta bancaria y confirma abajo.",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return DEPOSIT_CONFIRM

async def confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = context.user_data.get("deposit_amount", 0)
    await query.message.reply_text(f"Perfecto ✅, ahora envía el comprobante. Monto: ${amount:.2f}")
    return ConversationHandler.END

async def cancel_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# ConversationHandler para depósito
deposit_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(deposit_start, pattern="^deposit$")],
    states={
        DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)],
        DEPOSIT_CONFIRM: [CallbackQueryHandler(confirm_deposit, pattern="^confirm_deposit$"),
                          CallbackQueryHandler(cancel_deposit, pattern="^cancel_deposit$")]
    },
    fallbacks=[CallbackQueryHandler(cancel_deposit, pattern="^cancel_deposit$")]
)
