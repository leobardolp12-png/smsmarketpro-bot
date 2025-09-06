# bot/main.py
import os, logging, time
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from redis import Redis
from rq import Queue

from bot.db import engine, ensure_client, create_order
from bot.handlers import start, deposit_handler
from bot.utils import calculate_total, generate_captcha_options
from bot.utils.formatting import format_currency

# -------------------- CARGA DE VARIABLES --------------------
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

# In-memory sessions
SESSIONS = {}

# -------------------- CALLBACKS --------------------
async def callback_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    # Cancel deposit
    if data == 'cancel_deposit':
        SESSIONS.pop(uid, None)
        await query.edit_message_text('Depósito cancelado.')
        return

    # Confirm deposit
    if data == 'confirm_deposit':
        session = SESSIONS.get(uid)
        if not session or 'deposit_amount' not in session:
            await query.edit_message_text('No hay depósito pendiente.')
            return
        amount = session['deposit_amount']
        op_code = f'OP{int(time.time())}'
        with engine.connect() as conn:
            conn.execute(
                "INSERT INTO recargas (client_id, amount, status, operation_code) VALUES ((SELECT id FROM clients WHERE user_id=%s), %s, %s, %s)",
                (uid, amount, 'PENDING', op_code)
            )
        SESSIONS[uid] = {'state':'awaiting_receipt', 'operation_code':op_code}
        await context.bot.send_message(chat_id=uid, text=f'Envía el comprobante para la operación {op_code}.')
        await query.edit_message_text('Sube tu comprobante. La operación queda pendiente de revisión.')
        return

    # Orders
    if data.startswith('order_accept|'):
        parts = data.split('|')
        order_code = parts[1]
        with engine.begin() as conn:
            row = conn.execute("SELECT id, status FROM orders WHERE order_code=%s", (order_code,)).fetchone()
            if not row or row[1] != 'PENDING':
                await query.answer('No se pudo asignar (ya asignada).', show_alert=True)
                return
            op_user = uid
            res = conn.execute("SELECT id FROM operators WHERE user_id=%s", (op_user,)).fetchone()
            if not res:
                conn.execute("INSERT INTO operators (user_id, name) VALUES (%s, %s)", (op_user, query.from_user.username or 'Op'))
                res = conn.execute("SELECT id FROM operators WHERE user_id=%s", (op_user,)).fetchone()
            operator_db_id = res[0]
            conn.execute("UPDATE orders SET status=%s, operator_id=%s WHERE order_code=%s", ('ASSIGNED', operator_db_id, order_code))
        a,b,opts,correct = generate_captcha_options()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(str(opt), callback_data=f'captcha|{order_code}|{opt}|{correct}') for opt in opts]])
        await context.bot.send_message(chat_id=uid, text=f'Resolve el captcha: {a} + {b} = ?', reply_markup=kb)
        await query.answer('Te envié el captcha por privado')
        return

    # Captcha
    if data.startswith('captcha|'):
        _, order_code, chosen, correct = data.split('|')
        if int(chosen) == int(correct):
            await query.edit_message_text('Captcha correcto. Has aceptado la orden ' + order_code)
            await context.bot.send_message(chat_id=uid, text=f'Has aceptado la orden {order_code}. Envía el número ahora.')
        else:
            await query.edit_message_text('Captcha incorrecto. No se te asignó la orden.')
        return

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    if data == 'deposit':
        await context.bot.send_message(chat_id=uid, text="💰 ¿Cuánto deseas cargar?") 
        SESSIONS[uid] = {'state':'awaiting_deposit_amount'}
        return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or '').strip()
    session = SESSIONS.get(uid)
    if not session:
        await update.message.reply_text('Usa /start para ver el menú.')
        return

# -------------------- MAIN --------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler('start', start))
    app.add_handler(deposit_handler)

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_query_handler, pattern='^(deposit|sms|info|historial|perfil|referidos)$'))
    app.add_handler(CallbackQueryHandler(callback_actions, pattern=r'^(confirm_deposit|cancel_deposit|confirm_order|order_accept\|)'))
    app.add_handler(CallbackQueryHandler(callback_actions, pattern=r'^captcha\|'))

    # Mensajes
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling()

if __name__ == '__main__':
    main()
