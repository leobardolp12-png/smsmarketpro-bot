# worker/worker.py - RQ worker that processes background jobs (timeouts, reassignments)
import os
from redis import Redis
from rq import Worker, Queue, Connection
from dotenv import load_dotenv
load_dotenv()
REDIS_URL = os.getenv('REDIS_URL')
redis_conn = Redis.from_url(REDIS_URL)
listen = ['default']
if __name__ == '__main__':
    with Connection(redis_conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()
