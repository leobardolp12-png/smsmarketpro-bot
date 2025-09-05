# bot/db.py - simple SQLAlchemy sync helpers
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, BigInteger, String, Numeric, Text, TIMESTAMP, select, func
from sqlalchemy.sql import text
from sqlalchemy.exc import NoResultFound
import os
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL, echo=False)
metadata = MetaData()

clients = Table('clients', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', BigInteger, unique=True, nullable=False),
    Column('name', Text),
    Column('balance', Numeric, default=0),
    Column('orders_count', Integer, default=0),
    Column('created_at', TIMESTAMP)
)

operators = Table('operators', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', BigInteger, unique=True, nullable=False),
    Column('name', Text),
    Column('balance_retirable', Numeric, default=0),
    Column('accepted', Integer, default=0),
    Column('completed', Integer, default=0),
    Column('cancelled', Integer, default=0),
    Column('created_at', TIMESTAMP)
)

orders = Table('orders', metadata,
    Column('id', Integer, primary_key=True),
    Column('order_code', String, unique=True),
    Column('client_id', Integer),
    Column('app', Text),
    Column('quantity', Integer),
    Column('price_unit', Numeric),
    Column('total', Numeric),
    Column('status', Text),
    Column('operator_id', Integer),
    Column('created_at', TIMESTAMP),
    Column('updated_at', TIMESTAMP)
)

numbers = Table('numbers', metadata,
    Column('id', Integer, primary_key=True),
    Column('order_id', Integer),
    Column('number', Text),
    Column('app', Text),
    Column('operator_id', Integer),
    Column('status', Text),
    Column('created_at', TIMESTAMP)
)

recargas = Table('recargas', metadata,
    Column('id', Integer, primary_key=True),
    Column('client_id', Integer),
    Column('amount', Numeric),
    Column('status', Text),
    Column('operation_code', String),
    Column('receipt_path', Text),
    Column('created_at', TIMESTAMP)
)

def ensure_client(conn, user_id, name=None):
    sel = select([clients.c.id, clients.c.balance]).where(clients.c.user_id==user_id)
    res = conn.execute(sel).fetchone()
    if res:
        return res
    ins = clients.insert().values(user_id=user_id, name=name or 'Unknown', balance=0, orders_count=0)
    conn.execute(ins)
    return conn.execute(sel).fetchone()

def create_order(conn, user_id, app, quantity, price_unit, total):
    # create client if not exist
    cl = ensure_client(conn, user_id)
    # generate order code simple
    code = f"#%06d" % (int(func.floor(func.random()*1000000).compile(dialect=engine.dialect).execute() if False else 1))
    # fallback: use timestamp
    import time
    code = f"#%04d" % int(time.time()%10000)
    ins = orders.insert().values(order_code=code, client_id=cl[0], app=app, quantity=quantity, price_unit=price_unit, total=total, status='PENDING')
    conn.execute(ins)
    return code

