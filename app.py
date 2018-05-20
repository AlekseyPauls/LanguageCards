# -*- coding: utf-8 -*-

from flask import Flask, render_template, redirect, url_for, send_file, abort
from flask_socketio import SocketIO, join_room, leave_room, rooms
import random, os, glob, re, codecs, configparser, codecs
from mongoengine import *
from models import Room, Deck


app = Flask(__name__)
app.config['SECRET_KEY'] = 'jsbcfsbfjefebw237u3gdbdc'
socketio = SocketIO(app)

# Test Config
# MONGO = {
#     'db': 'mongo',
#     'host': 'localhost',
#     'port': '27017',
# }

#App Config
MONGO = {
    'db': 'mongo',
    'host': 'db',
    'port': '27017',
}

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://%(host)s:%(port)s/%(db)s' % MONGO)
db = connect(MONGO['db'], host=MONGO['host'])


""" Routing """


@app.route('/')
def start():
    return render_template('./StartPage.html')


@app.route('/room/<room_id>')
def room(room_id):
    if room_exists(room_id):
        return render_template('./RoomPage.html', room_id=room_id)
    else:
        abort(404)


@app.route('/create_deck')
def create_deck():
    return render_template('./CreateDeckPage.html')


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


# Add room_life_time check to delete useless rooms before create new
@socketio.on('start game')
def start_game(data):
    room = data['current_room']
    new_room = {}
    new_room['id'] = generate_room_id()
    new_room['decks'] = data['decks']
    new_room['clients'] = 0
    add_room(new_room)
    get_random_cards(new_room['id'])
    app.logger.debug('Created game room with id: ' + str(new_room['id']))
    socketio.emit('redirect', url_for('room', room_id=new_room['id']), room=room)


@socketio.on('redirect to CreateDeck')
def redirect_to_CreateDeck(room):
    socketio.emit('redirect', url_for('create_deck'), room=room)


@socketio.on('redirect to EditDeck')
def redirect_to_EditDeck(data):
    socketio.emit('redirect', url_for('edit_deck', name=data['deck']), room=data['room'])


""" Create deck page """


@socketio.on('save deck')
def save_deck(data):
    print(data)
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


""" Room page """


@socketio.on('join game room')
def join_game_room(room):
    join_room(room)
    increase_clients(room)


@socketio.on('leave game room')
def leave_game_room(room):
    leave_room(room)
    decrease_clients(room)

@socketio.on('send room settings')
def send_room_settings(room):
    try:
        config = configparser.RawConfigParser()
        config.read('settings.properties')
        sett = {'minCardsInRow': config['room']['minCardsInRow'],
                'defaultCardsInRow': config['room']['defaultCardsInRow'],
                'maxCardsInRow': config['room']['maxCardsInRow'],
                'stepCardsInRow': config['room']['stepCardsInRow'],
                'minCardHeight': config['room']['minCardHeight'],
                'defaultCardHeight': config['room']['defaultCardHeight'],
                'maxCardHeight': config['room']['maxCardHeight'],
                'stepCardHeight': config['room']['stepCardHeight'],
                'minCardFontSize': config['room']['minCardFontSize'],
                'defaultCardFontSize': config['room']['defaultCardFontSize'],
                'maxCardFontSize': config['room']['maxCardFontSize'],
                'stepCardFontSize': config['room']['stepCardFontSize']}
        socketio.emit('get room settings', sett, room=room)
    except Exception:
        app.logger.error('Error in config file')


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
    new_cards = get_random_cards(room)
    socketio.emit('get new cards', new_cards, room=room)


""" Common """


@socketio.on('join single room')
def join_single_room(room):
    join_room(room)
    app.logger.debug('Join to single room: ' + str(room))
    #app.logger.warning('A warning occurred (%d apples)', 42)
    #app.logger.error('An error occurred')


@socketio.on('redirect to Start')
def redirect_to_Start(room):
    print('redirect of ' + room)
    socketio.emit('redirect', url_for('start'), room=room)


@socketio.on('send languages')
def send_languages(room):
    lang = get_languages()
    socketio.emit('get languages', lang, room=room)


""" Database using """


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


def increase_clients(room_id):
    room = Room.objects(Q(name=room_id)).first()
    room.clients += 1
    app.logger.debug('Join game room: ' + str(room_id) + ". Current number of clients: " + str(room.clients))
    room.save()


def decrease_clients(room_id):
    room = Room.objects(Q(name=room_id)).first()
    room.clients -= 1
    app.logger.debug('Leave game room: ' + str(room_id) + ". Current number of clients: " + str(room.clients))
    if room.clients == 0:
        room.delete()
        app.logger.debug('Close game room: ' + str(room_id))
    else:
        room.save()


def add_room(room):
    new_room = Room(name=room['id'], decks=room['decks'],  clients=room['clients'])
    new_room.save()


def get_random_cards(room_id):
    room = Room.objects(Q(name=room_id)).first()
    cards = []
    for deck_name in room.decks:
        deck = Deck.objects(Q(name=deck_name)).first()
        card = random_card(deck.cards)
        cards.append(card)
    room.current_cards = cards
    room.save()
    return cards


def get_current_cards(room_id):
    room = Room.objects(Q(name=room_id)).first()
    return room.current_cards


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


""" Service logic """


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


def get_languages():
    lang_dict = {}
    path = "static/languages/"
    files = os.listdir(path)
    for filename in files:
        if (filename.count("_") == 0):
            lang_code = ""
        else:
            lang_code = filename[filename.find("_") + 1 : filename.find('.')]
        with codecs.open(path + filename, 'r', 'utf-8') as f:
            lines = f.readlines()
            if ((lines[0])[0] == '#' and is_properties(lines)):
                lang_dict[lang_code] = lines[0][1 : len(lines[0]) - 1]
            else:
                app.logger.debug("Wrong language file " + filename)
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
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
