# -*- coding: utf-8 -*-

import random, os, re, configparser, codecs, datetime, time
from mongoengine import *
from models import Room, Deck

from language_cards import app, pool, log, TIME_TO_LIVE, RECONNECTION_TIME


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


def delete_client(room, client):
    time.sleep(15)
    decrease_clients({'room': room, 'client': client})


def disconnect_client(client):
    for room in Room.objects():
        if client in room.clients:
            pool.add_task(decrease_clients_with_delay, {'room': room.name, 'client': client})


def decrease_clients_with_delay(room):
    time.sleep(RECONNECTION_TIME)
    decrease_clients(room)


def increase_clients(room_id):
    room = Room.objects(Q(name=room_id['room'])).first()
    room.clients.append(room_id['client'])
    log.info('Join game room: ' + str(room_id['room']) + ". Current clients: " + str(room.clients))
    room.save()


def decrease_clients(room_id):
    room = Room.objects(Q(name=room_id['room'])).first()
    if room_id['client'] in room.clients:
        room.clients.remove(room_id['client'])
        log.info('Leave game room: ' + str(room_id) + ". Current clients: " + str(room.clients))
        if len(room.clients) == 0:
            close_room(room_id['room'])
        else:
            room.save()


def close_room(room_id):
    room = Room.objects(Q(name=room_id)).first()
    room.delete()
    log.info('Close game room: ' + str(room_id))


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
    log.info('Created game room with id: ' + str(new_room['id']))
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
        if ((now - room.last_update).total_seconds()) > float(TIME_TO_LIVE):
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
        log.info('Error in config file')


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
    path = 'language_cards/static/languages/'
    files = os.listdir(path)
    for filename in files:
        if (filename.count('_') == 0):
            lang_code = ""
        else:
            lang_code = filename[filename.find('_') + 1: filename.find('.')]
        with codecs.open(path + filename, 'r', 'utf-8') as f:
            lines = f.readlines()
            if ((lines[0])[0] == '#' and is_properties(lines)):
                lang_dict[lang_code] = lines[0][1: len(lines[0]) - 1]
            else:
                log.info('Wrong language file ' + filename)
    return lang_dict


def is_properties(lines):
    for line in lines:
        if (line[0] == "#" or line[0] == "\n"):
            continue
        if (line.count("=") != 1):
            return False
    return True
