# -*- coding: utf-8 -*-

from flask import render_template, url_for, send_file, abort, request
from flask_socketio import join_room, leave_room
from flask_mobility.decorators import mobile_template
import os, glob
from mongoengine import *
from models import Room, Deck

from language_cards import app, socketio, DEBUG, HOST, PORT
import language_cards.service as serv


""" Routing """


@app.route('/')
@mobile_template('{mobile/}StartPage.html')
def start(template):
    print(os.listdir("/"))
    return render_template(template)


@app.route('/health')
def health():
    return "Service is health"


@app.route('/room/<room_id>')
@mobile_template('{mobile/}RoomPage.html')
def room(template, room_id):
    if serv.room_exists(room_id):
        return render_template(template, room_id=room_id)
    else:
        abort(404)


@app.route('/create_deck')
@mobile_template('{mobile/}CreateDeckPage.html')
def create_deck(template):
    return render_template(template)


@app.route('/create_room/<room_id>')
@mobile_template('{mobile/}CreateRoomPage.html')
def create_room(template, room_id):
    if serv.room_exists(room_id):
        return render_template(template, room_id=room_id)
    else:
        abort(404)


@app.route('/edit_deck/<name>')
@mobile_template('{mobile/}EditDeckPage.html')
def edit_deck(template, name):
    if serv.deck_exists(name):
        return render_template(template, name=name)
    else:
        abort(404)


@app.route('/decks/<name>')
def decks(name):
    deck_name = name[: name.rfind('.')]
    serv.make_tmp_file(deck_name)
    file = open('tmp/' + name, 'rb')
    return send_file(file, mimetype='text/')


""" Start page """


@socketio.on('send table')
def send_table(room):
    deck_list = serv.get_deck_list()
    socketio.emit('make table', deck_list, room=room)


@socketio.on('create room')
def start_room(data):
    room = data['current_room']
    new_room = {}
    new_room['id'] = serv.generate_room_id()
    new_room['decks'] = data['decks']
    serv.add_room(new_room)
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

    if (not serv.check_deck_name(deck['name'])):
        socketio.emit('message', 'message_bad_deckname', room=room)
        return
    if data.get('cards') is not None:
        deck['cards'].extend(serv.parse_cards(data['cards'], 'string'))
    if data.get('file') is not None:
        deck['cards'].extend(serv.parse_cards(data['file'], 'file'))
    deck['length'] = len(deck['cards'])
    if deck['length'] == 0:
        socketio.emit('message', 'message_empty_deck', room=room)
        return
    res = serv.save_deck_to_db(deck)
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

    deck['cards'].extend(serv.parse_cards(data['cards'], 'string'))
    deck['length'] = len(deck['cards'])
    serv.change_deck_in_db(deck)


@socketio.on('delete deck')
def delete_deck(name):
    serv.delete_deck_from_db(name)


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
    serv.set_settings(mes['room'], mes['settings'])


@socketio.on('start game')
def start_game(room):
    socketio.emit('redirect', url_for('room', room_id=room['room']), room=room['client'])


""" Room page """


@socketio.on('join game room')
def join_game_room(room):
    join_room(room['room'])
    serv.increase_clients(room)


@socketio.on('leave game room')
def leave_game_room(room):
    if not room['old']:
        leave_room(room['room'])
    serv.decrease_clients(room)


@socketio.on('send settings')
def send_settings(room):
    sett = serv.get_settings(room['room'])
    socketio.emit('get room settings', sett, room=room['client'])


@socketio.on('send view change settings')
def send_view_change_settings(room):
    sett = serv.get_default_settings()
    socketio.emit('get view change settings', sett, room=room['client'])


@socketio.on('prepare field')
def send_decks_count(data):
    room = Room.objects(Q(name=data['room'])).first()
    count = len(room.decks)
    socketio.emit('make field', count, room=data['client'])


@socketio.on('prepare cards')
def prepare_room(data):
    cards = serv.get_current_cards(data['room'])
    socketio.emit('get new cards', cards, room=data['client'])


@socketio.on('send new cards')
def send_new_cards(room):
    new_cards = serv.get_new_cards(room)
    socketio.emit('get new cards', new_cards, room=room)


@socketio.on('disconnect')
def disconnect():
    serv.disconnect_client(request.sid)


@socketio.on('mark up local storage')
def mark_up_local_storage(data):
    res = serv.mark_up_unused(data['locstore'])
    socketio.emit('delete unused settings', res, room=data['client'])


""" Common """


@socketio.on('redirect to Start')
def redirect_to_Start(room):
    socketio.emit('redirect', url_for('start'), room=room)


@socketio.on('send languages')
def send_languages(room):
    lang = serv.get_languages()
    socketio.emit('get languages', lang, room=room)


@socketio.on('send default settings')
def send_default_settings(room):
    sett = serv.get_default_settings()
    socketio.emit('get room settings', sett, room=room['client'])


""" Application """


if __name__ == '__main__':
    socketio.run(app, host=HOST, port=PORT, debug=DEBUG)
