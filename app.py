from flask import Flask, render_template, redirect, url_for, send_file, abort
from flask_socketio import SocketIO, join_room, leave_room, rooms
import random
import os

from mongoengine import *
from models import Room, Deck


app = Flask(__name__)
app.config['SECRET_KEY'] = 'jsbcfsbfjefebw237u3gdbdc'
socketio = SocketIO(app)

# Test Config
# MONGO = {
#                 'db': 'mongo',
#                 'host': 'localhost',
#                 'port': '27017',
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
    return render_template('./EditDeckPage.html', name=name)


""" Start page """


@socketio.on('send table')
def send_table(room):
    deck_list = get_deck_list()
    socketio.emit('make table', deck_list, room=room)


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
    room = room['room']
    socketio.emit('redirect', url_for('create_deck'), room=room)


""" Create deck page """


@socketio.on('save deck')
def save_deck(data):
    print(data)
    room = data['room']
    deck = {}
    deck['name'] = data['name']
    deck['description'] = data['description']
    deck['cards'] = []

    if data.get('cards') is not None:
        deck['cards'].extend(parse_cards(data['cards'], 'string'))

    if data.get('file') is not None:
        deck['cards'].extend(parse_cards(data['file'], 'file'))

    deck['length'] = len(deck['cards'])

    res = save_deck_to_db(deck)
    if res:
        socketio.emit('message', 'Deck was saved!', room=room)
    else:
        socketio.emit('message', 'Can`t save deck: name is already using', room=room)



""" Edit deck page """






""" Room page """


@socketio.on('join game room')
def join_game_room(room):
    join_room(room)
    app.logger.debug('Join to game room: ' + str(room))
    increase_clients(room)
    #print('Has entered the game room: ' + str(room) + '. Now clients: ' + str((rooms[room])['clients']))


@socketio.on('leave game room')
def on_leave(room):
    leave_room(room)
    decrease_clients(room)
    #print('Has leaved the room: ' + str(room) + '. Now clients: ' + str((rooms[room])['clients']))


# Where it needs?
@socketio.on('send deck info')
def send_deck_info(data):
    room = data['room']
    name = data['name']
    deck = Deck.objects(Q(name=name)).first()
    socketio.emit('get deck info', {'length': deck.length, 'description': deck.description}, room=room)


@socketio.on('prepare field')
def send_decks_count(data):
    room = Room.objects(Q(name=data['room'])).first()
    count = len(room.decks)
    socketio.emit('make field', count, room=data['client'])

# To do: send current cards only to new room
@socketio.on('prepare cards')
def prepare_room(data):
    cards = get_current_cards(data['room'])
    socketio.emit('get new cards', cards, room=data['client'])


@socketio.on('send new cards')
def send_new_cards(room):
    new_cards = get_random_cards(room)
    #print('New current card for room: ' + str(room) + ' ' + (rooms[room])['current card'])
    socketio.emit('get new cards', new_cards, room=room)


""" Common """


@socketio.on('join single room')
def join_single_room(room):
    join_room(room)
    #logging
    app.logger.debug('Join to single room: ' + str(room))
    #app.logger.warning('A warning occurred (%d apples)', 42)
    #app.logger.error('An error occurred')


@socketio.on('redirect to Start')
def redirect_to_Start(room):
    room = room['room']
    socketio.emit('redirect', url_for('start'), room=room)


""" Database using """


def room_exists(room_id):
    print("Exists room " + room_id)
    if Room.objects(Q(name=room_id)).first() is not None:
        return True
    else:
        return False


def increase_clients(room_id):
    room = Room.objects(Q(name=room_id)).first()
    room.clients += 1
    room.save()


def decrease_clients(room_id):
    room = Room.objects(Q(name=room_id)).first()
    room.clients -= 1
    # close room
    if room.clients == 0:
        room.delete()
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


""" Service logic """


def parse_cards(cards, mode):
    ret = []
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
                ret.append(str)
                str = ""
            else:
                ret.append(line)

    return ret


def generate_room_id():
    id = random.randint(0, 100000000)
    while Room.objects(Q(name=id)).first() is not None:
        id = random.randint(0, 100000000)
    return id


def random_card(cards):
    r = random.randint(0, len(cards) - 1)
    return cards[r]



""" Application """


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
