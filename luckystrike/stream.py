from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.python import log

import httpstream

class MessageReceiver(httpstream.MessageReceiver):

    """
    Receive Message from stream and callback the provided method else errback
    """

    def __init__(self, user_callback, user_errback, url):
        self.user_callback = user_callback
        self.user_errback = user_errback
        self.url = url

    def connectionMade(self):
        log.msg('started receiving messages from %s' % self.url)

    def connectionFailed(self, why):
        log.err('cannot connect to %s: %s' % (self.url, why))

    def messageReceived(self, message):
        d = Deferred()
        d.addCallback(self.user_callback)
        d.addErrback(self.user_errback)

        d.callback(message)

def listen(username, room_id, callback, errback):
    """
    Start Campfire live stream
    """
    url = 'https://streaming.campfirenow.com/room/%s/live.json' % room_id
    stream = httpstream.stream(reactor, url, MessageReceiver(callback, errback, url), username=username, password='X')

    return stream
