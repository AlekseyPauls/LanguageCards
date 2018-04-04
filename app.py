from flask import Flask, render_template, redirect, url_for, send_file
from flask_socketio import SocketIO, join_room, leave_room, rooms
import random
import os

from mongoengine import *
from models import Card, Deck


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


""" Routing """


@app.route('/cards/<deck_name><int:card>')
def cards(deck_name, card):
    deck = Deck.objects(Q(name=deck_name)).first()
    card = deck.cards[card]
    return send_file(card.image, mimetype='image')


@app.route('/base_card')
def base_card():
    base_card = open('static/1.png', 'rb')
    return send_file(base_card, mimetype='image')


@app.route('/')
def start():
    return render_template('./StartPage.html')


@app.route('/room/<int:room_id>')
def room(room_id):
    return render_template('./RoomPage.html', room_id=room_id)


@app.route('/create_deck')
def create_deck():
    return render_template('./CreateDeckPage.html')


@app.route('/edit_deck/<name>')
def edit_deck(name):
    return render_template('./EditDeckPage.html', name=name)


""" Start page """


@socketio.on('send table')
def send_table(room):
    deck_list = []
    for deck in Deck.objects():
        deck_list.append({'name': deck.name, 'length': deck.length, 'description': deck.description})
    print(deck_list)
    socketio.emit('make table', deck_list, room=room)


@socketio.on('start game')
def start_game(data):
    global rooms
    new_room = data['new room']
    room = data['current room']
    room_state = {}
    room_state['deck_name'] = data['deck_name']
    room_state['clients'] = 0
    room_state['current card'] = random_card(data['deck_name'])
    rooms[new_room] = room_state
    #print('Redirect to new room: ' + str(new_room) + '   ' + str(room))
    socketio.emit('redirect', url_for('room', room_id=new_room), room=room)


@socketio.on('redirect to CreateDeck')
def redirect_to_CreateDeck(room):
    room = room['room']
    socketio.emit('redirect', url_for('create_deck'), room=room)


""" Create deck page """


@socketio.on('save deck')
def save_deck(data):
    room = data['room']
    deck = {}
    deck['name'] = data['name']
    deck['description'] = data['description']
    deck['length'] = 0

    res = save_deck_to_db(deck)
    if res:
        socketio.emit('redirect', url_for('edit_deck', name=deck['name']), room=room)
    else:
        socketio.emit('message', 'Can`t save deck: name is already using', room=room)



""" Edit deck page """


@socketio.on('save card')
def save_card(data):
    room = data['room']
    save_card_to_db(data)
    deck = Deck.objects(Q(name=data['deck_name'])).first()
    socketio.emit('get deck info', {'length': deck.length, 'description': deck.description}, room=room)



""" Room page """\


@socketio.on('join game room')
def join_game_room(room):
    global rooms
    join_room(room)
    (rooms[room])['clients'] += 1
    #print('Has entered the game room: ' + str(room) + '. Now clients: ' + str((rooms[room])['clients']))


@socketio.on('leave game room')
def on_leave(room):
    global rooms
    leave_room(room)
    (rooms[room])['clients'] -= 1
    #print('Has leaved the room: ' + str(room) + '. Now clients: ' + str((rooms[room])['clients']))


@socketio.on('send deck info')
def send_deck_infok(data):
    room = data['room']
    name = data['name']
    deck = Deck.objects(Q(name=name)).first()
    socketio.emit('get deck info', {'length': deck.length, 'description': deck.description}, room=room)


@socketio.on('prepare room')
def prepare_room(room):
    card = (rooms[room])['current card']
    #print('Prepare room: ' + str(room) + '   ' + card)
    socketio.emit('get new card', {'text': card['text'], 'image': card['image']}, room=room)


@socketio.on('send new card')
def send_new_card(room):
    global rooms
    new_card = random_card((rooms[room])['deck_name'])
    (rooms[room])['current card'] = new_card
    #print('New current card for room: ' + str(room) + ' ' + (rooms[room])['current card'])
    socketio.emit('get new card', {'text': new_card['text'], 'image': new_card['image']}, room=room)


""" Common """


@socketio.on('join single room')
def join_single_room(room):
    join_room(room)
    #logging
    app.logger.debug('A value for debugging')
    app.logger.warning('A warning occurred (%d apples)', 42)
    app.logger.error('An error occurred')
    #print('Has entered the single room: ' + str(room))


@socketio.on('redirect to Start')
def redirect_to_Start(room):
    room = room['room']
    socketio.emit('redirect', url_for('start'), room=room)


""" Database using """


def random_card(deck_name):
    deck = Deck.objects(Q(name=deck_name)).first()
    r = random.randint(0, deck.length - 1)
    card = deck.cards[r]
    if card.image:
        return {'text': card.text, 'image': url_for('cards', deck_name=deck_name, card=r)}
    else:
        return {'text': card.text, 'image': ''}


def get_deck_list():
    deck_list = []
    for deck in Deck.objects():
        deck_list.append({'name': deck.name, 'length': deck.length})
    return deck_list


def save_deck_to_db(deck):
    if Deck.objects(Q(name=deck['name'])).first() is not None:
        return False
    new_deck = Deck(name=deck['name'], description=deck['description'], length=deck['length'])
    new_deck.save()
    return True


def save_card_to_db(card):
    new_card = Card(text=card['text'])
    if card['image'] != '':
      new_card.image.put(card['image'], content_type = 'image/')
    deck = Deck.objects(Q(name=card['deck_name'])).first()
    deck.cards.append(new_card)
    deck.length += 1
    deck.save()


def get_cards(deck_name):
    deck = Deck.objects(Q(name=deck_name)).first()
    return deck.cards


""" Application """


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
