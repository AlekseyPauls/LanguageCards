# -*- coding: utf-8 -*-

from flask import Flask, render_template, url_for, send_file, abort, request
from flask_socketio import SocketIO, join_room, leave_room
import random, os, glob, re, configparser, codecs, datetime, time, sys, logging, json_logging
from mongoengine import *
from models import Room, Deck
from queue import Queue
from threading import Thread


""" Init section """


app = Flask(__name__)

# Read config
try:
    config = configparser.RawConfigParser()
    config.read('settings.properties')
    ptm = float(config['app']['socketPingTimeout'])
    sk = config['app']['secretKey']
    rct = float(config['app']['reconnectionTime'])
    pw = int(config['app']['poolWorkers'])
    ttl = config['room']['timeToLive']
    MONGO = {
        'db': config['db']['db'],
        'host': config['db']['host'],
        'port':  config['db']['port'],
    }
except Exception:
    app.logger.error('Error in config file. Set default settings')
    ptm = float(300)
    sk = 'jsbcfsbfjefebw237u3gdbdc'
    rct = 15
    pw = 3
    MONGO = {
        'db': 'mongo',
        'host': 'db',
        'port': '27017',
    }

app.config['SECRET_KEY'] = sk
socketio = SocketIO(app, ping_timeout=ptm)

# Logging
json_logging.ENABLE_JSON_LOGGING = True
json_logging.init(framework_name='flask')
json_logging.init_request_instrument(app)
logger = logging.getLogger("test-logger")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

# Database
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://%(host)s:%(port)s/%(db)s' % MONGO)
db = connect(MONGO['db'], host=MONGO['host'])


""" Routing """


@app.route('/')
def start():
    return render_template('./StartPage.html')


@app.route('/health')
def health():
    return "Service is health"


@app.route('/room/<room_id>')
def room(room_id):
    if room_exists(room_id):
        return render_template('./RoomPage.html', room_id=room_id)
    else:
        abort(404)


@app.route('/m.room/<room_id>')
def m_room(room_id):
    if room_exists(room_id):
        return render_template('./MobileRoomPage.html', room_id=room_id)
    else:
        abort(404)


@app.route('/create_deck')
def create_deck():
    return render_template('./CreateDeckPage.html')


@app.route('/create_room/<room_id>')
def create_room(room_id):
    if room_exists(room_id):
        return render_template('./CreateRoomPage.html', room_id=room_id)
    else:
        abort(404)


@app.route('/edit_deck/<name>')
def edit_deck(name):
    if deck_exists(name):
        return render_template('./EditDeckPage.html', name=name)
    else:
        abort(404)


@app.route('/decks/<name>')
def decks(name):
    deck_name = name[: name.rfind('.')]
    make_tmp_file(deck_name)
    file = open('tmp/' + name, 'rb')
    return send_file(file, mimetype='text/')


""" Start page """


@socketio.on('send table')
def send_table(room):
    deck_list = get_deck_list()
    socketio.emit('make table', deck_list, room=room)


@socketio.on('create room')
def start_room(data):
    room = data['current_room']
    new_room = {}
    new_room['id'] = generate_room_id()
    new_room['decks'] = data['decks']
    add_room(new_room)
    app.logger.debug('Created game room with id: ' + str(new_room['id']))
    #logger.info('Created game room with id: ' + str(new_room['id']))
    socketio.emit('redirect', url_for('create_room', room_id=new_room['id']), room=room)


@socketio.on('redirect to CreateDeck')
def redirect_to_CreateDeck(room):
    socketio.emit('redirect', url_for('create_deck'), room=room)


@socketio.on('redirect to EditDeck')
def redirect_to_EditDeck(data):
    socketio.emit('redirect', url_for('edit_deck', name=data['deck']), room=data['room'])


""" Create deck page """


@socketio.on('save deck')
def save_deck(data):
    room = data['room']
    deck = {}
    deck['name'] = data['name']
    deck['description'] = data['description']
    deck['cards'] = []

    if (not check_deck_name(deck['name'])):
        socketio.emit('message', 'message_bad_deckname', room=room)
        return
    if data.get('cards') is not None:
        deck['cards'].extend(parse_cards(data['cards'], 'string'))
    if data.get('file') is not None:
        deck['cards'].extend(parse_cards(data['file'], 'file'))
    deck['length'] = len(deck['cards'])
    if deck['length'] == 0:
        socketio.emit('message', 'message_empty_deck', room=room)
        return
    res = save_deck_to_db(deck)
    if res:
        socketio.emit('message', 'message_deck_saved', room=room)
    else:
        socketio.emit('message', 'message_deckname_is_using', room=room)


""" Edit deck page """


@socketio.on('send deck info')
def send_deck_info(data):
    room = data['room']
    name = data['name']
    deck = Deck.objects(Q(name=name)).first()
    socketio.emit('get deck info', {'description': deck.description, 'cards': deck.cards}, room=room)


@socketio.on('change deck')
def change_deck(data):
    deck = {}
    deck['name'] = data['deck']
    deck['cards'] = []

    deck['cards'].extend(parse_cards(data['cards'], 'string'))
    deck['length'] = len(deck['cards'])
    change_deck_in_db(deck)


@socketio.on('delete deck')
def delete_deck(name):
    delete_deck_from_db(name)


@socketio.on('clear tmp')
def clear_tmp():
    files = glob.glob('tmp/*')
    for f in files:
        os.remove(f)


""" Create room page """


@socketio.on('close game room')
def close_game_room(room):
    close_game_room(room)


@socketio.on('update settings')
def update_settings(mes):
    set_settings(mes['room'], mes['settings'])


@socketio.on('start game')
def start_game(room):
    socketio.emit('redirect', url_for('room', room_id=room['room']), room=room['client'])


""" Room page """


@socketio.on('join game room')
def join_game_room(room):
    join_room(room['room'])
    increase_clients(room)


@socketio.on('leave game room')
def leave_game_room(room):
    if not room['old']:
        leave_room(room['room'])
    decrease_clients(room)


@socketio.on('send settings')
def send_settings(room):
    sett = get_settings(room['room'])
    socketio.emit('get room settings', sett, room=room['client'])


@socketio.on('send view change settings')
def send_view_change_settings(room):
    sett = get_default_settings()
    socketio.emit('get view change settings', sett, room=room['client'])


@socketio.on('prepare field')
def send_decks_count(data):
    room = Room.objects(Q(name=data['room'])).first()
    count = len(room.decks)
    socketio.emit('make field', count, room=data['client'])


@socketio.on('prepare cards')
def prepare_room(data):
    cards = get_current_cards(data['room'])
    socketio.emit('get new cards', cards, room=data['client'])


@socketio.on('send new cards')
def send_new_cards(room):
    new_cards = get_new_cards(room)
    socketio.emit('get new cards', new_cards, room=room)


@socketio.on('disconnect')
def disconnect():
    disconnect_client(request.sid)


@socketio.on('mark up local storage')
def mark_up_local_storage(data):
    res = mark_up_unused(data['locstore'])
    socketio.emit('delete unused settings', res, room=data['client'])


""" Common """


@socketio.on('redirect to Start')
def redirect_to_Start(room):
    socketio.emit('redirect', url_for('start'), room=room)


@socketio.on('send languages')
def send_languages(room):
    lang = get_languages()
    socketio.emit('get languages', lang, room=room)


@socketio.on('send default settings')
def send_default_settings(room):
    sett = get_default_settings()
    socketio.emit('get room settings', sett, room=room['client'])


""" Database using """


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


def room_exists(room_id):
    if Room.objects(Q(name=room_id)).first() is not None:
        return True
    else:
        return False


def deck_exists(name):
    if Deck.objects(Q(name=name)).first() is not None:
        return True
    else:
        return False


def generate_room_id():
    id = random.randint(0, 100000000)
    while Room.objects(Q(name=id)).first() is not None:
        id = random.randint(0, 100000000)
    return id


def delete_client(room, client):
    time.sleep(15)
    decrease_clients({'room': room, 'client': client})


def disconnect_client(client):
    for room in Room.objects():
        if client in room.clients:
            pool.add_task(decrease_clients_with_delay, {'room': room.name, 'client': client})


def decrease_clients_with_delay(room):
    time.sleep(rct)
    decrease_clients(room)


def increase_clients(room_id):
    room = Room.objects(Q(name=room_id['room'])).first()
    room.clients.append(room_id['client'])
    app.logger.debug('Join game room: ' + str(room_id['room']) + ". Current clients: " + str(room.clients))
    #logger.info('Join game room: ' + str(room_id['room']) + ". Current clients: " + str(room.clients))
    room.save()


def decrease_clients(room_id):
    room = Room.objects(Q(name=room_id['room'])).first()
    if room_id['client'] in room.clients:
        room.clients.remove(room_id['client'])
        app.logger.debug('Leave game room: ' + str(room_id) + ". Current clients: " + str(room.clients))
        #logger.info('Leave game room: ' + str(room_id) + ". Current clients: " + str(room.clients))
        if len(room.clients) == 0:
            close_room(room_id['room'])
        else:
            room.save()


def close_room(room_id):
    room = Room.objects(Q(name=room_id)).first()
    room.delete()
    app.logger.debug('Close game room: ' + str(room_id))
    #logger.info('Close game room: ' + str(room_id))


def set_settings(room_id, settings):
    room = Room.objects(Q(name=room_id)).first()
    room.settings = settings
    room.save()


def get_settings(room_id):
    room = Room.objects(Q(name=room_id)).first()
    return room.settings


def add_room(room):
    decks = []
    current_numbers = []
    for deckname in room['decks']:
        deck = Deck.objects(Q(name=deckname)).first()
        cards = deck.cards
        random.shuffle(cards)
        if len(cards) > 1:
            decks.append(cards)
        else:
            l = []
            l.append(cards)
            decks.append(l)
        current_numbers.append(0)
    time = datetime.datetime.utcnow
    new_room = Room(name=room['id'], decks=decks, current_numbers=current_numbers, last_update=time)
    new_room.save()
    delete_old_rooms()


def get_new_cards(room_id):
    room = Room.objects(Q(name=room_id)).first()
    cards = []
    cur_nbs = room.current_numbers
    decks = room.decks
    for i in range(len(room.decks)):
        if cur_nbs[i] + 1 < len(decks[i]):
            cards.append(decks[i][cur_nbs[i] + 1])
            cur_nbs[i] += 1
        else:
            sorted_cards = room.decks[i]
            random_sort(sorted_cards)
            room.decks[i] = sorted_cards
            cards.append(sorted_cards[0])
            cur_nbs[i] = 0
    room.current_numbers = cur_nbs
    room.save()
    renew_room_last_update(room_id)
    return cards


def get_current_cards(room_id):
    room = Room.objects(Q(name=room_id)).first()
    current_cards = []
    cur_nbs = room.current_numbers
    decks = room.decks
    for i in range(len(room.decks)):
        current_cards.append(decks[i][cur_nbs[i]])
    renew_room_last_update(room_id)
    return current_cards


def get_deck_list():
    deck_list = []
    for deck in Deck.objects():
        deck_list.append({'name': deck.name, 'length': deck.length, 'description': deck.description})
    return deck_list


def save_deck_to_db(deck):
    if Deck.objects(Q(name=deck['name'])).first() is not None:
        return False
    new_deck = Deck(name=deck['name'], description=deck['description'], length=deck['length'], cards=deck['cards'])
    new_deck.save()
    return True


def change_deck_in_db(deck):
    changing_deck = Deck.objects(Q(name=deck['name'])).first()
    changing_deck.cards = deck['cards']
    changing_deck.length = deck['length']
    changing_deck.save()


def delete_deck_from_db(deck):
    deleting_deck = Deck.objects(Q(name=deck)).first()
    deleting_deck.delete()


def make_tmp_file(name):
    deck = Deck.objects(Q(name=name)).first()
    file = open('tmp/' + name + '.txt', 'w')
    descr = deck.description.split('\n')
    for line in descr:
        file.write('#' + line + '\n')
    for line in deck.cards:
        file.write(line + '\n')
    return file


def renew_room_last_update(room_id):
    room = Room.objects(Q(name=room_id)).first()
    room.last_update = datetime.datetime.utcnow
    room.save()


def delete_old_rooms():
    now = datetime.datetime.utcnow()
    for room in Room.objects():
        if ((now - room.last_update).total_seconds()) > float(ttl):
            room.delete()


def mark_up_unused(locstore):
    res = {}
    for s in locstore:
        if s.find('previousSocket') != -1 or s.find('settings') != -1:
            room_id = re.findall('(\d+)', s)[0]

            if Room.objects(Q(name=room_id)).first() is not None:
                res[s] = True
            else:
                res[s] = False
    return res


""" Service logic """


def get_default_settings():
    try:
        config = configparser.RawConfigParser()
        config.read('settings.properties')
        sett = {'minCardWidth': config['room']['minCardWidth'],
            'defaultCardWidth': config['room']['defaultCardWidth'],
            'maxCardWidth': config['room']['maxCardWidth'],
            'stepCardWidth': config['room']['stepCardWidth'],
            'minCardHeight': config['room']['minCardHeight'],
            'defaultCardHeight': config['room']['defaultCardHeight'],
            'maxCardHeight': config['room']['maxCardHeight'],
            'stepCardHeight': config['room']['stepCardHeight'],
            'minCardFontSize': config['room']['minCardFontSize'],
            'defaultCardFontSize': config['room']['defaultCardFontSize'],
            'maxCardFontSize': config['room']['maxCardFontSize'],
            'stepCardFontSize': config['room']['stepCardFontSize']}
        return sett
    except Exception:
        app.logger.error('Error in config file')
        #logger.info('Error in config file')


def check_deck_name(name):
    if len(name) == 0:
        return False
    r = re.findall(r'[\W]+', name)
    if len(r) == 0:
        return True
    else:
        return False


def parse_cards(cards, mode):
    ret = []
    # Magic for right decoding of special symbols
    cards = cards.encode('latin-1').decode('utf-8')
    if mode == 'file':
        tmp = cards.decode('utf-8').split('\n')
    else :
        tmp = cards.split('\n')
    str = ""
    for line in tmp:
        if len(line) == 0:
            continue
        if line[len(line) - 1] == '/':
            str = str + line[:len(line) - 1] + '\n'
        else:
            if str != "":
                str = str + line
                ret.append(str.encode('latin-1').decode('utf-8'))
                str = ""
            else:
                ret.append(line)
    return ret


def random_card(cards):
    r = random.randint(0, len(cards) - 1)
    return cards[r]


def random_sort(cards):
    random.shuffle(cards)


def get_languages():
    lang_dict = {}
    path = 'static/languages/'
    files = os.listdir(path)
    for filename in files:
        if (filename.count('_') == 0):
            lang_code = ""
        else:
            lang_code = filename[filename.find('_') + 1 : filename.find('.')]
        with codecs.open(path + filename, 'r', 'utf-8') as f:
            lines = f.readlines()
            if ((lines[0])[0] == '#' and is_properties(lines)):
                lang_dict[lang_code] = lines[0][1 : len(lines[0]) - 1]
            else:
                app.logger.debug('Wrong language file ' + filename)
                #logger.info('Wrong language file ' + filename)
    return lang_dict


def is_properties(lines):
    for line in lines:
        if (line[0] == "#" or line[0] == "\n"):
            continue
        if (line.count("=") != 1):
            return False
    return True


""" Application """


if __name__ == '__main__':
    # ThreadPool
    pool = ThreadPool(3)
    # App
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
