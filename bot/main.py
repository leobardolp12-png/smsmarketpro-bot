# bot/main.py - minimal bot integrating Postgres + Redis (RQ)
import os, logging, time
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from bot.db import engine, ensure_client, create_order
from rq import Queue
from redis import Redis
from bot.utils import calculate_total, generate_captcha_options

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip()]
GROUP_ORDERS_ID = int(os.getenv('GROUP_ORDERS_ID','0') or 0)
GROUP_RECARGAS_ID = int(os.getenv('GROUP_RECARGAS_ID','0') or 0)
PRICE_PER_SMS = float(os.getenv('PRICE_PER_SMS','10'))
OPERATOR_PAYOUT = float(os.getenv('OPERATOR_PAYOUT_PER_CODE','8'))
REDIS_URL = os.getenv('REDIS_URL')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis queue for background tasks
redis_conn = Redis.from_url(REDIS_URL)
q = Queue('default', connection=redis_conn)

# simple in-memory sessions
SESSIONS = {}

def start_kb():
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('DEPOSITAR SALDO', callback_data='deposit')],
        [InlineKeyboardButton('SMS', callback_data='sms'), InlineKeyboardButton('INFO', callback_data='info')],
        [InlineKeyboardButton('HISTORIAL', callback_data='historial')],
        [InlineKeyboardButton('PERFIL', callback_data='perfil'), InlineKeyboardButton('REFERIDOS', callback_data='referidos')]
    ])
    return kb

from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards import start_kb
from bot.db import engine, ensure_client
from bot.utils.formatting import format_currency

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Intentamos registrar o recuperar al cliente
    try:
        with engine.begin() as conn:
            client = ensure_client(conn, user.id, user.first_name, user.username)
            saldo = client.get("saldo", 0)
    except Exception as e:
        print(f"Error al verificar/crear cliente: {e}")
        saldo = 0  # fallback seguro

    # Mensaje de bienvenida
    welcome_text = (
        f"👋 ¡Hola @{user.username or user.first_name}! Bienvenido a SMSMarketProBot 🚀\n\n"
        f"💰 Tu saldo actual: {format_currency(saldo)}\n\n"
        "Este bot te permite pedir SMS para tus apps de verificación, de forma rápida, económica y sin complicaciones.\n\n"
        "👇 ¿Qué deseas hacer ahora?"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_text,
        reply_markup=start_kb()
    )
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    if data == 'deposit':
        await context.bot.send_message(chat_id=uid, text="¿Cuánto deseas cargar? (ej. 100)") 
        SESSIONS[uid] = {'state':'awaiting_deposit_amount'}
        return
    if data == 'sms':
        await context.bot.send_message(chat_id=uid, text="¿Para qué app necesitas SMS?") 
        SESSIONS[uid] = {'state':'awaiting_order_app'}
        return
    if data == 'perfil':
        with engine.connect() as conn:
            sel = conn.execute("SELECT orders_count, balance FROM clients WHERE user_id=%s", (uid,)).fetchone()
            if sel:
                await context.bot.send_message(chat_id=uid, text=f"📦 Códigos pedidos: {sel[0]}\n💰 Saldo: ${sel[1]}") 
            else:
                await context.bot.send_message(chat_id=uid, text="Perfil no encontrado.")
        return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or '').strip()
    session = SESSIONS.get(uid)
    if not session:
        await update.message.reply_text('Usa /start para ver el menú.')
        return
    state = session.get('state')
    if state == 'awaiting_deposit_amount':
        try:
            amount = float(text)
        except:
            await update.message.reply_text('Monto inválido. Intenta de nuevo.')
            return
        session['deposit_amount'] = amount
        SESSIONS[uid] = session
        kb = InlineKeyboardMarkup([[InlineKeyboardButton('Confirmar depósito', callback_data='confirm_deposit')],[InlineKeyboardButton('Cancelar', callback_data='cancel_deposit')]])
        await update.message.reply_text(f"Realiza la transferencia a: BANCO XXXX\nReferencia: TU_USER_{uid}", reply_markup=kb)
        return
    if state == 'awaiting_order_app':
        session['order_app'] = text
        session['state'] = 'awaiting_order_qty'
        SESSIONS[uid] = session
        await update.message.reply_text('¿Cuántos SMS necesitas?')
        return
    if state == 'awaiting_order_qty':
        try:
            qty = int(text)
        except:
            await update.message.reply_text('Cantidad inválida.')
            return
        app_name = session.get('order_app')
        total, price_unit = calculate_total(qty, PRICE_PER_SMS)
        session['order_qty'] = qty
        session['state'] = 'awaiting_order_confirm'
        SESSIONS[uid] = session
        kb = InlineKeyboardMarkup([[InlineKeyboardButton('Confirmar pedido', callback_data='confirm_order')],[InlineKeyboardButton('Cancelar', callback_data='cancel_order')]])
        await update.message.reply_text(f"Resumen:\nApp: {app_name}\nCantidad: {qty}\nPrecio unitario: ${price_unit}\nTotal: ${total}", reply_markup=kb)
        return
    await update.message.reply_text('No hay flujo activo.')

async def callback_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    if data == 'cancel_deposit':
        SESSIONS.pop(uid, None)
        await query.edit_message_text('Depósito cancelado.')
        return
    if data == 'confirm_deposit':
        session = SESSIONS.get(uid)
        if not session or 'deposit_amount' not in session:
            await query.edit_message_text('No hay depósito pendiente.')
            return
        # create recarga record (simple insert)
        amount = session['deposit_amount']
        op_code = f'OP{int(time.time())}'
        with engine.connect() as conn:
            conn.execute("INSERT INTO recargas (client_id, amount, status, operation_code) VALUES ((SELECT id FROM clients WHERE user_id=%s), %s, %s, %s)", (uid, amount, 'PENDING', op_code))
        SESSIONS[uid] = {'state':'awaiting_receipt','operation_code':op_code}
        await context.bot.send_message(chat_id=uid, text=f'Envía el comprobante para la operación {op_code}.')
        await query.edit_message_text('Sube tu comprobante por favor. La operación queda pendiente de revisión.')
        return
    if data == 'confirm_order':
        session = SESSIONS.get(uid)
        if not session or 'order_qty' not in session:
            await query.edit_message_text('No hay pedido pendiente.')
            return
        qty = session['order_qty']
        app_name = session['order_app']
        total, price_unit = calculate_total(qty, PRICE_PER_SMS)
        with engine.connect() as conn:
            code = create_order(conn, uid, app_name, qty, price_unit, total)
        await query.edit_message_text(f'✅ Tu orden {code} fue creada. Te notificaremos cuando un operador la acepte.')
        kb = InlineKeyboardMarkup([[InlineKeyboardButton('Aceptar pedido', callback_data=f'order_accept|{code}')]])
        await context.bot.send_message(chat_id=GROUP_ORDERS_ID, text=f'Nueva orden {code}\nApp: {app_name}\nCantidad: {qty}\nTotal: ${total}\nCliente: {uid}', reply_markup=kb)
        SESSIONS.pop(uid, None)
        return
    if data and data.startswith('order_accept|'):
        parts = data.split('|')
        order_code = parts[1]
        # assign order atomically (simplified): check status and update
        with engine.begin() as conn:
            row = conn.execute("SELECT id, status FROM orders WHERE order_code=%s", (order_code,)).fetchone()
            if not row or row[1] != 'PENDING':
                await query.answer('No se pudo asignar (ya asignada).', show_alert=True)
                return
            # set assigned and operator (operator is query.from_user.id)
            # map operator user_id to operators.id or create if not exists
            op_user = uid
            res = conn.execute("SELECT id FROM operators WHERE user_id=%s", (op_user,)).fetchone()
            if not res:
                conn.execute("INSERT INTO operators (user_id, name) VALUES (%s, %s)", (op_user, query.from_user.username or 'Op'))
                res = conn.execute("SELECT id FROM operators WHERE user_id=%s", (op_user,)).fetchone()
            operator_db_id = res[0]
            conn.execute("UPDATE orders SET status=%s, operator_id=%s WHERE order_code=%s", ('ASSIGNED', operator_db_id, order_code))
        # send captcha to operator
        a,b,opts,correct = generate_captcha_options()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(str(opt), callback_data=f'captcha|{order_code}|{opt}|{correct}') for opt in opts]])
        await context.bot.send_message(chat_id=uid, text=f'Resolve el captcha: {a} + {b} = ?', reply_markup=kb)
        await query.answer('Te envié el captcha por privado')
        return
    if data and data.startswith('captcha|'):
        _, order_code, chosen, correct = data.split('|')
        if int(chosen) == int(correct):
            await query.edit_message_text('Captcha correcto. Has aceptado la orden ' + order_code)
            await context.bot.send_message(chat_id=uid, text=f'Has aceptado la orden {order_code}. Envía el número ahora.')
        else:
            await query.edit_message_text('Captcha incorrecto. No se te asignó la orden.')
        return

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    session = SESSIONS.get(uid)
    if not session or session.get('state') != 'awaiting_receipt':
        await update.message.reply_text('No hay ninguna operación pendiente de comprobante.')
        return
    op = session.get('operation_code')
    # save file locally
    file = await update.message.photo[-1].get_file()
    os.makedirs('receipts', exist_ok=True)
    path = f"receipts/{op}_{uid}.jpg"
    await file.download_to_drive(custom_path=path)
    # mark recarga receipt path
    with engine.connect() as conn:
        conn.execute("UPDATE recargas SET receipt_path=%s WHERE operation_code=%s", (path, op))
    kb = InlineKeyboardMarkup([[InlineKeyboardButton('Aceptar saldo', callback_data=f'recargas_accept|{op}')],[InlineKeyboardButton('Rechazar', callback_data=f'recargas_reject|{op}')]])
    await context.bot.send_message(chat_id=GROUP_RECARGAS_ID, text=f'Nuevo comprobante\nOp: {op}\nUser: {uid}\nMonto: {session.get("deposit_amount")}', reply_markup=kb)
    await update.message.reply_text('Comprobante enviado a revisión. Tu saldo será agregado si se acepta.')
    SESSIONS.pop(uid, None)

async def recargas_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('recargas_accept|'):
        op = data.split('|')[1]
        with engine.begin() as conn:
            row = conn.execute("SELECT client_id, amount FROM recargas WHERE operation_code=%s", (op,)).fetchone()
            if not row:
                await query.edit_message_text('Operación no encontrada.')
                return
            client_id, amount = row
            conn.execute("UPDATE recargas SET status=%s WHERE operation_code=%s", ('ACCEPTED', op))
            conn.execute("UPDATE clients SET balance = balance + %s WHERE id=%s", (amount, client_id))
            # notify client: get user_id
            uid_row = conn.execute("SELECT user_id FROM clients WHERE id=%s", (client_id,)).fetchone()
            if uid_row:
                await context.bot.send_message(chat_id=int(uid_row[0]), text=f'💰 Se agregaron ${amount} a tu saldo, ya puedes crear ordenes.') 
        await query.edit_message_text('Recarga aceptada y saldo agregado.')
        return
    if data.startswith('recargas_reject|'):
        op = data.split('|')[1]
        with engine.connect() as conn:
            row = conn.execute("SELECT client_id FROM recargas WHERE operation_code=%s", (op,)).fetchone()
            if row:
                uid_client = conn.execute("SELECT user_id FROM clients WHERE id=%s", (row[0],)).fetchone()[0]
                kb = InlineKeyboardMarkup([[InlineKeyboardButton('Intentar nuevamente', callback_data='deposit')]])
                await context.bot.send_message(chat_id=int(uid_client), text='Tu recarga fue rechazada. Por favor verifica y vuelve a intentar.', reply_markup=kb)
        await query.edit_message_text('Recarga rechazada.')
        return

async def addoperator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text('No autorizado')
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text('Uso: /addoperator <user_id>')
        return
    uid = int(args[0])
    with engine.connect() as conn:
        conn.execute("INSERT INTO operators (user_id, name) VALUES (%s, %s)", (uid, 'Op'))
    await update.message.reply_text(f'Operador {uid} agregado.')

async def cancelarorden(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text('No autorizado')
        return
    args = context.args
    if not args:
        await update.message.reply_text('Uso: /cancelarorden <order_code>')
        return
    ocode = args[0]
    with engine.connect() as conn:
        conn.execute("UPDATE orders SET status=%s WHERE order_code=%s", ('CANCELLED', ocode))
    await update.message.reply_text(f'Orden {ocode} cancelada.')

from bot.handlers import start, deposit_handler


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(deposit_handler)
    app.add_handler(CallbackQueryHandler(callback_query_handler, pattern='^(deposit|sms|info|historial|perfil|referidos)$'))
    app.add_handler(CallbackQueryHandler(callback_actions, pattern='^(confirm_deposit|cancel_deposit|confirm_order|order_accept\|)'))
    app.add_handler(CallbackQueryHandler(recargas_actions, pattern='^recargas_'))
    app.add_handler(CallbackQueryHandler(callback_actions, pattern='^captcha\|'))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CommandHandler('addoperator', addoperator))
    app.add_handler(CommandHandler('cancelarorden', cancelarorden))
    app.run_polling()

if __name__ == '__main__':
    main()
