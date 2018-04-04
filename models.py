from mongoengine import *


class Card(EmbeddedDocument):
    image = FileField()
    text = StringField()

class Deck(Document):
    #Id = IntField()
    name = StringField()
    description = StringField()
    length = IntField()
    cards = EmbeddedDocumentListField(Card)
