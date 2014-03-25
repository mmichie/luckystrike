LuckyStrike
===========

A Campfire to IRC bridge, in the spirit of [camper_van](https://github.com/zerowidth/camper_van),
written in Python.

LuckyStrike is not yet fully featured, but it does support the following
operations:

    IRC                         Campfire
    ---                         --------
    #day_job                    "Day Job" room
    joe_bob (nick)              Joe Bob (user)

    /LIST                       List rooms
    /JOIN #day_job              Join the "Day Job" room
    /PART #day_job              Leave the "Day Job" room
    /TOPIC #day_job new topic   Change room's topic to "new topic"

Dependencies
============

  * Python 2.7
  * [Pinder](https://github.com/rhymes/pinder)
  * [Twisted](https://twistedmatrix.com/trac/)
  * [PyCrypto](https://www.dlitz.net/software/pycrypto/)
  * [pyOpenSSL](https://github.com/pyca/pyopenssl)
  * [pyasn1](http://pyasn1.sourceforge.net/)

SSL keys
========

openssl genrsa > keys/server.key

openssl req -new -x509 -key keys/server.key -out keys/server.crt -days 1000

License
========

MIT, see LICENSE for details.

Contributing
============

Fork, patch, test, pull request.
