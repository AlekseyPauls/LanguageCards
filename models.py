from mongoengine import *


class Deck(Document):
    #Id = IntField()
    name = StringField()
    description = StringField()
    cards = ListField()
    length = IntField()

    def to_dict(self):
        #entity_dict = dict(Id=self.Id, name=self.name, cards=self.cards)
        entity_dict = dict(name=self.name, cards=self.cards)
        return entity_dict

    def __repr__(self):
        return '<Entity: "{}">'.format(self.name)
