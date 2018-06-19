from mongoengine import *


class Room(Document):
    name = IntField()
    decks = ListField(ListField())
    current_numbers = ListField()
    clients = ListField()
    last_update = DateTimeField()
    settings = DictField()


class Deck(Document):
    name = StringField()
    description = StringField()
    length = IntField()
    cards = ListField()
