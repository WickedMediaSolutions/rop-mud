# -*- coding: utf-8 -*-
"""
Connection screen

This is the text to show the user when they first connect to the game (before
they log in).

To change the login screen in this module, do one of the following:

- Define a function `connection_screen()`, taking no arguments. This will be
  called first and must return the full string to act as the connection screen.
  This can be used to produce more dynamic screens.
- Alternatively, define a string variable in the outermost scope of this module
  with the connection string that should be displayed. If more than one such
  variable is given, Evennia will pick one of them at random.

The commands available to the user when the connection screen is shown
are defined in evennia.default_cmds.UnloggedinCmdSet. The parsing and display
of the screen is done by the unlogged-in "look" command.

"""

from django.conf import settings

from evennia import utils

CONNECTION_SCREEN = r"""
|x540               .                    .                      .          |n
|x540          .       *        .    .         .         *       .   |n
|x540     .        .     .       ___====-_  _-====___    .        .      |n
|x540        .           *   _-~~####### ~~   ~~ ###~~-  *       .        |n
|x540     .            _-~##########~ _-~##~~    -.   ~-.         .     |n
|x540               _-~##########~~ _-~##~~   -~#~-    ~~-.     .      |n
|x540    .         _-~##########~~ _-~##~~  _-~##~-.  ~~~~~-.          |n
|x540       .    _-~##########~~ _-~~##~  _-~####~~-.   ~~  ~~-.       |n
|x540          _-~##########~~ _-~##~~    _-~###~~-.     ~~~  ~-.    |n
|x540  .     _-~##########~~_-~~##       _-~##~~  -.    .~~~ ~~-.      |n
|x540      .-=~#########~~ _-~##~-.     _-~###~~   --. .~ ~~~. |n
|x540     -=~~########~~ _-~##~~       _-~####~~     -.    ~.~  ~-.   |n
|x540    -=~~~~#####~~  _-~##~-.      _-~#####~~--..~~.   .~~~~ ~~-.   |n
|x540   -=~~~~~~###~ .-=~~##~~         _-~#######~~-.  ~~~  ~~~~~ ~~-.  |n
|x540  -=~~~ ~~~~-.=~~#####           _-~##########~~  .~~~~  ~~~~~ ~~-|n
|x540  -~~~~ ~~~.-=~~#####             -=~##########~~ ~~~~~ ~~~~~ ~~~-.|n
|x540  .~~~~~ ~~.-=~~#####               -=~##########~~  ~~~~~  ~~~~~-|n
|x540   .~~~  ~~.-=~~###                  -=~~#########~~  ~~~~~  ~~~~-.|n
|x540    ~~~~ .-==~~~###                    -=~~#########~~  ~~~ ~~~~~-|n
|x540    ~~~.=~==~. -=~##                    -=~~#########~~-  ~~~~~~~-|n
|x540    ~~~.~=~~=- . -=~#                    -=~~##########~-. ~~~~~~-|n
|x540    ~~.-=~~~=-  -=~~=                    -=~~###########~-.~~~~~-|n
|x540    ~.-=~~~~  .~==~~~=-                 -=~~############~-.~~~~~-|n
|x540    ~,-~~~  -=~~~ ===~~~=-             -=~~#############~-.~~~~-|n
|x540    ,~~~,-=~.  .==~~~~~===~~--_____--~~==~############~~-.~~~-|n
|x540   ,~~~,-=~~  ==~,~=~~~~~~~=======~~~~~~~~~~##########~~-.~~~-|n
|x540   ,~~~,=~~~ .-=~ ~=~~~~~======~~~-==~~~~~~###########~~-.~~~-|n
|x540   ,~~,-=~~  =~=..~=~~~~~=======~~~========~~~~~--~~~~  .~~~|n
|x540   ,~~,-=~~  ~~~ .~=~~~~~~~~~~~~~====-..~~.......       ~~~|n
|x540   ,~.-=~~  ~~~ .~=~~~~~~~~~~~~~~~~~~.......:::...      ~~~|n
|x540                  -=~=~~~~~~~~~......::...........                     |n
|x540              -=~~~=~~~~~~....... .|r*          *|n .               |n
|x540                -=~==~~~~~~.......    |r*    *|n              |n
|x540               -=~~~==~~~~...... .    |r* *|n                  |n
|x540             -=~==~~~=~~~~......   .  |r*|n                     |n
|x540           -=~~~~==~~~~~~.....           			   |n
|x540         -=~~==~~~~~~~~.....              			   |n
|x540        -=~~~~~~~~~~~~....          			   |n
|x540      -=~~~~~~~~~~~~~~~.....       |[501          -=~~=~|n       |n
|x540     -=~~~~=~~~~~~~~~~~......     |[501   -=~~~~~=~~~~~-|n       |n
|x540                         ...... ::..                       |n
|x540                         .  .... ::.. |R  -=~|n     .            |n
|x540                   .     .  ..... ::..                   .            |n
|x540           .              .... ::...               .         |n
|x540             .    .     .... ::...      .    .                       |n
|x540                        .... ::...                                    |n
|x540                  .    ... ::...         .              |n
|x540           .         ..  ::..  ______                 .          |n
|x540  .          .       .   ..::..  |m-=|R*|m=-|n      .       .              . |n
|x540    .          .         .... |m-==|R*|m==-|n    .         .           |n
|x540      .        .      ..... |m-====|R*|m====-|n   .        .        |n
|x540   .         .      ........ |m-=======|R*|m=======-|n  .      .    |n
|x540             .         ...... |m-=========|R*|m=========-|n                     |n
|x540                .      ......|m-===========|R*|m===========-|n                  |n
|x540              . . . .......  |m========|R* * * * * * * * *|m========|n  |n
|n
|n
|w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |R* |w~~~~~~ |n
|n
|n
|Y                      R I T E S   O F   P A S S A G E                      |n
|n
|n
|R                     EVERY ADVENTURE BEGINS IN THE DIRT                          |n
|n
|y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |R* |y~~~~ |n
|n
|n
|C           Through darkness, we forge our destiny...|n
|n
|n
 If you have an existing account, connect to it by typing:
      |wconnect <username> <password>|n
 If you need to create an account, type (without the <>'s):
      |wcreate <username> <password>|n

 If you have spaces in your username, enclose it in quotes.
 Enter |whelp|n for more info. |wlook|n will re-show this screen.
|n
|n""".format(
    settings.SERVERNAME, utils.get_evennia_version("short")
)