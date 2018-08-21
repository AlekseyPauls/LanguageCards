===========
Description
===========

This is an application to help with online lessons in foreign languages. Participants can join a pre-established game room to see cards with words or pictures that are the same for everyone and perform assignments by verbal agreement.

=======================
Usage and configuration
=======================

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

To set the standard settings for the view of cards and also the limits of their modification by user, edit the section "room" in the file "settings.properties".

--------------
Other settings
--------------

File "settings.properties", "app" section:

socketPingTimeout (integer) - shows how long (in seconds) the server will wait before next update of the socket on the client. For the user, this is seen as the page freeze for 2-3 seconds.
So, it is recommended to set this value for a long period (300). Short ping time is justified only with a small amount of memory for storing room records in the database (in this case,
the player will leave the room faster and rooms will be deleted more often).

secretKey (string) - key for flask application, must be unique.

reconnectionTime (integer) - delay (in seconds) before deleting user from room. At this time the user can reconnect successfully.
For example, if all players got internet connection problem and in the server set short reconnectionTime, room may be deleted before at least one user can reconnect.
But this functional uses thread pool and long reconnectionTime can slow processing of user disconnect from room and this will lead to more frequent removal of rooms.

poolWorkers - caunt of workers in thread pool, which processing user disconnecting.

File "settings.properties", "db" section:

db - database name in MongoDB instance.

host - host of MongoDB instance.

port - port of MongoDB instance.

File "settings.properties", "room" section:

"timeToLive" - time of room live. Every room has attribute "last_update", which updated when something new happens in the room.
When the new room is created, all old rooms are checked. If more time elapsed before the date of rooms "last_update" than in the "timeToLive", this room is removed.
