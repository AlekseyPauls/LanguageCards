# -*- coding: utf-8 -*-

from flask import Flask
from flask_socketio import SocketIO
from flask_mobility import Mobility
import os, configparser, logging, logmatic
from mongoengine import *
from queue import Queue
from threading import Thread


app = Flask(__name__)


try:
    config = configparser.RawConfigParser()
    config.read('settings.properties')
    PING_TIMEOUT = float(config['app']['socketPingTimeout'])
    SECRET_KEY = config['app']['secretKey']
    RECONNECTION_TIME = float(config['app']['reconnectionTime'])
    POOL_WORKERS = int(config['app']['poolWorkers'])
    TIME_TO_LIVE = config['room']['timeToLive']
    DEBUG = bool(config['app']['debug'])
    HOST = config['app']['host']
    PORT = int(config['app']['port'])
    MONGO = {
        'db': config['db']['db'],
        'host': config['db']['host'],
        'port':  config['db']['port'],
    }
except Exception:
    print("Can`t read the settings.properties")
    PING_TIMEOUT = float(300)
    SECRET_KEY = 'jsbcfsbfjefebw237u3gdbdc'
    RECONNECTION_TIME = 15
    POOL_WORKERS = 3
    TIME_TO_LIVE = 30000
    DEBUG = False
    HOST = "0.0.0.0"
    PORT = 5000
    MONGO = {
        'db': 'mongo',
        'host': 'db',
        'port': '27017',
    }

app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app, ping_timeout=PING_TIMEOUT)
Mobility(app)

# Logging
log = logging.getLogger("logger")
handler = logging.FileHandler("logs.log")
handler.setFormatter(logmatic.JsonFormatter())
log.addHandler(handler)
log.setLevel(logging.INFO)

# Database
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://%(host)s:%(port)s/%(db)s' % MONGO)
db = connect(MONGO['db'], host=MONGO['host'])


class Worker(Thread):
    def __init__(self, queue):
        super(Worker, self).__init__()
        self.q = queue
        self.daemon = True
        self.start()

    def run(self):
        while True:
            f, args, kwargs = self.q.get()
            try:
                f(*args, **kwargs)
                print(self.getName())
            except Exception as e:
                self.q.task_done()


class ThreadPool(object):
    def __init__(self, n=3):
        self.q = Queue(n)
        for _ in range(n):
            Worker(self.q)

    def add_task(self, f, *args, **kwargs):
        self.q.put((f, args, kwargs))


pool = ThreadPool(POOL_WORKERS)
