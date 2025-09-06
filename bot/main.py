# bot/main.py - SMSMarketProBot
import os
import logging
import time
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from bot.db import engine, ensure_client, create_order
from bot.utils import calculate_total, generate_captcha_options, format_currency
from redis import Redis
from rq import Queue

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
GROUP_ORDERS_ID = int(os.getenv("GROUP_ORDERS_ID", "0"))
GROUP_RECARGAS_ID = int(os.getenv("GROUP_RECARGAS_ID", "0"))
PRICE_PER_SMS = float(os.getenv("PRICE_PER_SMS", "10"))
REDIS_URL = os.getenv("REDIS_URL")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis queue
redis_conn = Redis.from_url(REDIS_URL)
q = Queue("default", connection=redis_conn)

# Sesiones en memoria
SESSIONS = {}

# --- Teclado principal ---
def start_kb():
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("DEPOSITAR SALDO", callback_data="deposit")],
        [InlineKeyboardButton("SMS", callback_data="sms"), InlineKeyboardButton("INFO", callback_data="info")],
        [InlineKeyboardButton("HISTORIAL", callback_data="historial")],
        [InlineKeyboardButton("PERFIL", callback_data="perfil"), InlineKeyboardButton("REFERIDOS", callback_data="referidos")]
    ])
    return kb

# --- Handlers Async ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        with engine.begin() as conn:
            client = ensure_client(conn, user.id, user.first_name, user.username)
            saldo = client.get("saldo", 0)
    except Exception as e:
        logger.error(f"Error al verificar/crear cliente: {e}")
        saldo = 0

    text = (
        f"👋 ¡Hola @{user.username or user.first_name}! Bienvenido a SMSMarketProBot 🚀\n\n"
        f"💰 Tu saldo actual: {format_currency(saldo)}\n\n"
        "Este bot te permite pedir SMS para tus apps de verificación.\n\n"
        "👇 ¿Qué deseas hacer ahora?"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=start_kb())

# --- ConversationHandler para depósito ---
DEPOSIT_AMOUNT, DEPOSIT_CONFIRM = range(2)

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
        await update.message.reply_text("❌ Ingresa un número válido mayor a 0.")
        return DEPOSIT_AMOUNT

    context.user_data["deposit_amount"] = amount
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Confirmar depósito", callback_data="confirm_deposit")],
        [InlineKeyboardButton("Cancelar", callback_data="cancel_deposit")]
    ])
    await update.message.reply_text(
        f"Envía ${amount:.2f} a nuestra cuenta:\nBanco: XXXX\nCuenta: 12345678\nCLABE: 012345678901234567",
        reply_markup=kb
    )
    return DEPOSIT_CONFIRM

async def confirm_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = context.user_data.get("deposit_amount", 0)
    await query.message.reply_text(f"✅ Perfecto, envía el comprobante de depósito. Monto: ${amount:.2f}")
    return ConversationHandler.END

async def cancel_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# --- Callback Query Handler principal ---
async def callback_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    # Cancelar depósito
    if data == "cancel_deposit":
        SESSIONS.pop(uid, None)
        await query.edit_message_text("Depósito cancelado.")
        return

    # Confirmar depósito simple
    if data == "confirm_deposit":
        amount = context.user_data.get("deposit_amount", 0)
        await query.edit_message_text(f"Depósito pendiente. Monto: ${amount}")
        return

    # Otros callbacks como sms, perfil, order_accept, captcha, etc.
    # Aquí puedes agregar la lógica de tus flujos existentes

# --- Main ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Comandos básicos
    app.add_handler(CommandHandler("start", start))

    # ConversationHandler para depósitos
    deposit_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(deposit_callback, pattern="^deposit$")],
        states={
            DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)],
            DEPOSIT_CONFIRM: [CallbackQueryHandler(confirm_deposit_callback, pattern="^confirm_deposit$")]
        },
        fallbacks=[CallbackQueryHandler(cancel_deposit_callback, pattern="^cancel_deposit$")]
    )
    app.add_handler(deposit_handler)

    # Callback general
    app.add_handler(CallbackQueryHandler(callback_actions, pattern=".*"))

    app.run_polling()

if __name__ == "__main__":
    main()
