# bot/main.py
import os, logging, time
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from bot.db import engine, ensure_client, create_order
from bot.utils import calculate_total, generate_captcha_options, format_currency

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip()]
GROUP_ORDERS_ID = int(os.getenv('GROUP_ORDERS_ID','0') or 0)
GROUP_RECARGAS_ID = int(os.getenv('GROUP_RECARGAS_ID','0') or 0)
PRICE_PER_SMS = float(os.getenv('PRICE_PER_SMS','10'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- In-memory sessions ---
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
DEPOSIT_AMOUNT, DEPOSIT_CONFIRM, ORDER_APP, ORDER_QTY, ORDER_CONFIRM = range(5)

# --- Start ---
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

# --- Depósitos ---
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

# --- Órdenes ---
async def sms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📱 ¿Para qué app necesitas SMS?")
    SESSIONS[query.from_user.id] = {'state':'awaiting_order_app'}

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or '').strip()
    session = SESSIONS.get(uid)
    if not session:
        await update.message.reply_text("Usa /start para ver el menú.")
        return

    state = session.get('state')
    if state == 'awaiting_order_app':
        session['order_app'] = text
        session['state'] = 'awaiting_order_qty'
        SESSIONS[uid] = session
        await update.message.reply_text("¿Cuántos SMS necesitas?")
        return

    if state == 'awaiting_order_qty':
        try:
            qty = int(text)
        except ValueError:
            await update.message.reply_text("Cantidad inválida.")
            return
        app_name = session.get('order_app')
        total, price_unit = calculate_total(qty, PRICE_PER_SMS)
        session['order_qty'] = qty
        session['state'] = 'awaiting_order_confirm'
        SESSIONS[uid] = session
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton('Confirmar pedido', callback_data='confirm_order')],
            [InlineKeyboardButton('Cancelar', callback_data='cancel_order')]
        ])
        await update.message.reply_text(f"Resumen:\nApp: {app_name}\nCantidad: {qty}\nPrecio unitario: ${price_unit}\nTotal: ${total}", reply_markup=kb)
        return

    await update.message.reply_text("No hay flujo activo.")

async def callback_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == 'cancel_order':
        SESSIONS.pop(uid, None)
        await query.edit_message_text("Pedido cancelado.")
        return

    if data == 'confirm_order':
        session = SESSIONS.get(uid)
        if not session:
            await query.edit_message_text("No hay pedido pendiente.")
            return
        qty = session['order_qty']
        app_name = session['order_app']
        total, price_unit = calculate_total(qty, PRICE_PER_SMS)
        with engine.connect() as conn:
            code = create_order(conn, uid, app_name, qty, price_unit, total)
        await query.edit_message_text(f"✅ Tu orden {code} fue creada.")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Aceptar pedido", callback_data=f"order_accept|{code}")]])
        await context.bot.send_message(chat_id=GROUP_ORDERS_ID, text=f"Orden {code}\nApp: {app_name}\nCantidad: {qty}\nTotal: ${total}\nCliente: {uid}", reply_markup=kb)
        SESSIONS.pop(uid, None)

    if data.startswith('order_accept|'):
        parts = data.split('|')
        order_code = parts[1]
        await query.answer(f"Has aceptado la orden {order_code} (ejemplo, lógica real)")

    if data.startswith('captcha|'):
        await query.answer("Captcha recibido (ejemplo, lógica real)")

# --- Main ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler('start', start))

    # ConversationHandlers
    app.add_handler(deposit_handler)

    # CallbackQueryHandlers
    app.add_handler(CallbackQueryHandler(sms_callback, pattern='^sms$'))
    app.add_handler(CallbackQueryHandler(callback_actions, pattern=r'^(confirm_order|cancel_order|order_accept\|.*|captcha\|.*)$'))

    # Mensajes
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Arranca
    app.run_polling()

if __name__ == "__main__":
    main()
