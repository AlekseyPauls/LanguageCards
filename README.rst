==============
Language cards
==============

---
Run
---

docker-compose up

--------------------
Internationalization
--------------------

To add a new locale you should create file with name and extension "UI_xx.properties" in directory "static/languages", where "xx" is two letter code of new locale.
Copy the content from "UI.properties" in your file and rewrite names of buttons, labels and other elements.
In the first string after "#" is the name of language which shows in application.
Pay attention on the length of the new names - it should not exceed the length of the names in the example.

---------------------------------
General application view settings
---------------------------------

To change these settings, edit the file "static/css/styles.css". This file contains detailed comments.

------------------
Card view settings
------------------

To set the standard settings for the view of cards and also the limits of their modification by user, edit the file "settings.properties".

--------------
Other settings
--------------

Settings.properties:

"timeToLive" - the of room live. Every room has attribute "last_update", which updated when something new happens in the room.
When the new room is created, all old rooms are checked. If more time elapsed before the date of rooms "last_update" than in the "timeToLive", this room is removed.