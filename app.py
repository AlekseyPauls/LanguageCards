from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, rooms
import random
import os

from mongoengine import *
from models import Deck


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


rooms = {}


@app.route('/')
def start():
    return render_template('./StartPage.html')


@app.route('/room/<int:room_id>')
def room(room_id):
    return render_template('./RoomPage.html', room_id=room_id)


@app.route('/create_deck')
def create_deck():
    return render_template('./CreateDeckPage.html')


@socketio.on('start game')
def start_game(data):
    global rooms
    new_room = data['new room']
    room = data['current room']
    room_state = {}
    room_state['deck_name'] = data['deck_name']
    room_state['clients'] = 0
    room_state['current card'] = get_cards(data['deck_name'])[0]
    rooms[new_room] = room_state
    #print('Redirect to new room: ' + str(new_room) + '   ' + str(room))
    socketio.emit('redirect', {'url': url_for('room', room_id=new_room)}, room=room)


@socketio.on('redirect to CreateDeck')
def redirect_to_CreateDeck(room):
    room = room['room']
    socketio.emit('redirect', {'url': url_for('create_deck')}, room=room)


@socketio.on('redirect to Start')
def redirect_to_Start(room):
    room = room['room']
    socketio.emit('redirect', {'url': url_for('start')}, room=room)


@socketio.on('save deck')
def save_deck(data):
    room = data['room']
    cards = data['cards'].split('\n')
    deck = {}
    deck['name'] = data['name']
    deck['description'] = data['description']
    deck['cards'] = cards
    deck['length'] = len(cards)

    res = save_to_db(deck)
    if res:
        socketio.emit('message', 'Deck was saved!', room=room)
    else:
        socketio.emit('message', 'Can`t save deck: name is already using', room=room)


@socketio.on('prepare room')
def prepare_room(room):
    card = (rooms[room])['current card']
    #print('Prepare room: ' + str(room) + '   ' + card)
    socketio.emit('get state', card, room=room)


@socketio.on('join single room')
def join_single_room(room):
    join_room(room)
    #print('Has entered the single room: ' + str(room))


@socketio.on('join game room')
def join_game_room(room):
    global rooms
    join_room(room)
    (rooms[room])['clients'] += 1
    #print('Has entered the game room: ' + str(room) + '. Now clients: ' + str((rooms[room])['clients']))


@socketio.on('send table')
def send_table(room):
    deck_list = []
    for deck in Deck.objects():
        deck_list.append({'name': deck.name, 'length': deck.length, 'description': deck.description})
    print(deck_list)
    socketio.emit('make table', deck_list, room=room)


@socketio.on('leave game room')
def on_leave(room):
    global rooms
    leave_room(room)
    (rooms[room])['clients'] -= 1
    #print('Has leaved the room: ' + str(room) + '. Now clients: ' + str((rooms[room])['clients']))


@socketio.on('send new card')
def send_new_card(room):
    global rooms
    new_card = random_card(get_cards((rooms[room])['deck_name']))
    (rooms[room])['current card'] = new_card
    #print('New current card for room: ' + str(room) + ' ' + (rooms[room])['current card'])
    socketio.emit('get new card', new_card, room=room)



def random_card(cards):
    return random.choice(cards)


def get_deck_list():
    deck_list = []
    for deck in Deck.objects():
        deck_list.append({'name': deck.name, 'length': deck.length})
    return deck_list


def save_to_db(deck):
    if Deck.objects(Q(name=deck['name'])).first() is not None:
        return False
    new_deck = Deck(deck['name'], deck['description'], deck['cards'], deck['length'])
    new_deck.save()
    return True

def get_cards(deck_name):
    deck = Deck.objects(Q(name=deck_name)).first()
    return deck.cards


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
