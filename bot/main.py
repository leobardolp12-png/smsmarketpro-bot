# bot/main.py
import os, logging, time
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from bot.db import engine, ensure_client, create_order
from bot.utils import calculate_total, generate_captcha_options, format_currency

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip()]
GROUP_ORDERS_ID = int(os.getenv('GROUP_ORDERS_ID','0') or 0)
GROUP_RECARGAS_ID = int(os.getenv('GROUP_RECARGAS_ID','0') or 0)
PRICE_PER_SMS = float(os.getenv('PRICE_PER_SMS','10'))
OPERATOR_PAYOUT = float(os.getenv('OPERATOR_PAYOUT_PER_CODE','8'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory sessions
SESSIONS = {}

# --- Keyboards ---
def start_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('DEPOSITAR SALDO', callback_data='deposit')],
        [InlineKeyboardButton('SMS', callback_data='sms'), InlineKeyboardButton('INFO', callback_data='info')],
        [InlineKeyboardButton('HISTORIAL', callback_data='historial')],
        [InlineKeyboardButton('PERFIL', callback_data='perfil'), InlineKeyboardButton('REFERIDOS', callback_data='referidos')]
    ])

# --- Estados ConversationHandler ---
DEPOSIT_AMOUNT, DEPOSIT_CONFIRM = range(2)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        with engine.begin() as conn:
            client = ensure_client(conn, user.id, user.first_name, user.username)
            saldo = client.get("saldo", 0)
    except:
        saldo = 0

    welcome_text = (
        f"👋 ¡Hola @{user.username or user.first_name}! Bienvenido a SMSMarketProBot 🚀\n\n"
        f"💰 Tu saldo actual: {format_currency(saldo)}\n\n"
        "Este bot te permite pedir SMS para tus apps de verificación.\n\n"
        "👇 ¿Qué deseas hacer ahora?"
    )

    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_text, reply_markup=start_kb())

# --- Deposits ---
async def deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("❌ Por favor, ingresa un número válido mayor a 0.")
        return DEPOSIT_AMOUNT

    context.user_data["deposit_amount"] = amount
    keyboard = [
        [InlineKeyboardButton("Confirmar depósito", callback_data="confirm_deposit")],
        [InlineKeyboardButton("Cancelar", callback_data="cancel_deposit")]
    ]
    await update.message.reply_text(
        f"Envía la cantidad de ${amount:.2f} a nuestra cuenta bancaria:\nBanco: XXXX\nCuenta: 12345678\nCLABE: 012345678901234567",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DEPOSIT_CONFIRM

async def confirm_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = context.user_data.get("deposit_amount", 0)
    await query.message.reply_text(f"Perfecto ✅, ahora envía el comprobante de depósito como imagen o archivo. Monto: ${amount:.2f}")
    return ConversationHandler.END

async def cancel_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

deposit_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(deposit_callback, pattern='^deposit$')],
    states={
        DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)],
        DEPOSIT_CONFIRM: [
            CallbackQueryHandler(confirm_deposit_callback, pattern='^confirm_deposit$'),
            CallbackQueryHandler(cancel_deposit_callback, pattern='^cancel_deposit$')
        ]
    },
    fallbacks=[]
)

# --- Callbacks generales ---
async def callback_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data.startswith('order_accept|'):
        await query.answer("Orden aceptada (ejemplo, agregar lógica real)")
    elif data.startswith('captcha|'):
        await query.answer("Captcha (ejemplo, agregar lógica real)")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    if data == 'sms':
        await context.bot.send_message(chat_id=uid, text="¿Para qué app necesitas SMS?")
    elif data == 'perfil':
        await context.bot.send_message(chat_id=uid, text="Perfil ejemplo")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mensaje recibido, flujo aún no implementado.")

# --- Main ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler('start', start))
    app.add_handler(deposit_handler)

    # CallbackQueryHandlers
    app.add_handler(CallbackQueryHandler(callback_query_handler, pattern='^(deposit|sms|info|historial|perfil|referidos)$'))
    app.add_handler(CallbackQueryHandler(callback_actions, pattern=r'^(confirm_deposit|cancel_deposit|confirm_order|order_accept\|)$'))

    # Mensajes
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Arranca bot
    app.run_polling()

if __name__ == "__main__":
    main()
