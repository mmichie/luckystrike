import pinder
import json
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.python import log

import httpstream

class MessageReceiver(httpstream.MessageReceiver):

    def __init__(self, user_callback, user_errback, url):
        self.user_callback = user_callback
        self.user_errback = user_errback
        self.url = url

    def connectionMade(self):
        log.msg('connected to %s' % self.url)

    def connectionFailed(self, why):
        log.err('cannot connect to %s: %s' % (self.url, why))

    def messageReceived(self, message):
        d = Deferred()
        d.addCallback(self.user_callback)
        d.addErrback(self.user_errback)

        d.callback(message)

def listen(username, room_id, callback, errback):

    url = 'https://streaming.campfirenow.com/room/%s/live.json' % room_id
    stream = httpstream.stream(reactor, url, MessageReceiver(callback, errback, url), username=username, password='X')

    return stream

def success(x):
    log.msg(x)

def failure(x):
    log.err(x)

if __name__ == '__main__':
    global campfire

    log.startLogging(sys.stdout)

    try:
        config_file = open('../config.json')
        config = dict(json.loads(config_file.read()))
        users = config['users']

        # connect to Campfire
        campfire = pinder.Campfire(config['domain'], config['api_key'])
        room = campfire.find_room_by_name('TCC')
        room.join()
        httpstream.stream(reactor, 'https://streaming.campfirenow.com/room/540835/live.json', MessageReceiver(success, failure), username=config['api_key'], password='X')
        reactor.run()
    except:
        log.err()
