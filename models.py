from mongoengine import *


class Room(Document):
    name = IntField()
    decks = ListField()
    current_cards = ListField()
    clients = IntField()


class Deck(Document):
    #Id = IntField()
    name = StringField()
    description = StringField()
    length = IntField()
    cards = ListField()
