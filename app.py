from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, rooms
import random

app = Flask(__name__)

app.config['SECRET_KEY'] = 'jsbcfsbfjefebw237u3gdbdc'
socketio = SocketIO(app)


rooms = {}


@app.route('/')
def start():
    return render_template('./StartPage.html')


@app.route('/room/<int:room_id>')
def room(room_id):
    return render_template('./Room.html', room_id=room_id)


@socketio.on('get deck')
def handle_my_custom_event1(data):
    global rooms
    deck = data['deck'].split('\n')
    new_room = data['new room']
    room = data['current room']
    room_state = {}
    room_state['deck'] = deck
    room_state['clients'] = 0
    room_state['current word'] = deck[0]
    rooms[new_room] = room_state
    #print('Redirect to new room: ' + str(new_room) + '   ' + str(room))
    socketio.emit('redirect', {'url': url_for('room', room_id=new_room)}, room=room)


@socketio.on('prepare room')
def prepare_room(room):
    deck = (rooms[room])['deck']
    word = (rooms[room])['current word']
    #print('Prepare room: ' + str(room) + '   ' + word)
    socketio.emit('get state', {'deck' : deck, 'word' : word}, room=room)


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


@socketio.on('leave game room')
def on_leave(room):
    global rooms
    leave_room(room)
    (rooms[room])['clients'] -= 1
    #print('Has leaved the room: ' + str(room) + '. Now clients: ' + str((rooms[room])['clients']))


@socketio.on('send new word')
def send_new_word(room):
    global rooms
    new_word = random_word((rooms[room])['deck'])
    (rooms[room])['current word'] = new_word
    #print('New current word for room: ' + str(room) + ' ' + (rooms[room])['current word'])
    socketio.emit('get new word', new_word, room=room)



def random_word(deck):
    return random.choice(deck)


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)