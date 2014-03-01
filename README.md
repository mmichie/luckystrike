luckystrike
===========

Campfire &lt;-> IRC proxy


SSL keys
========

openssl genrsa > keys/server.key
openssl req -new -x509 -key keys/server.key -out keys/server.crt -days 1000
