import pinder
import base64
import json
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.protocols import basic
from twisted.python import log
from twisted.python.failure import DefaultException
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

USER_AGENT = 'LuckyStrike'

def cbRequest(response, callback, errback):
    # We should look at the response headers here and figure out what to do on error
    protocol = JSONParser(callback, errback)
    response.deliverBody(protocol)

    return protocol.done

class JSONParser(basic.LineReceiver):
    delimiter = '\r'

    def __init__(self, user_callback, user_errback):
        self.done = Deferred()
        self.user_callback = user_callback
        self.user_errback = user_errback

    def lineReceived(self, line):
        d = Deferred()
        d.addCallback(self.user_callback)
        d.addErrback(self.user_errback)

        try:
            line = unicode(line.strip(), 'UTF-8')
            if len(line) > 0:
                d.callback(json.loads(line))
        except:
            log.err('Bad JSON: %s %s %s' % (len(line), line, [ord(c) for c in line]))

        def connectionLost(self, reason):
            if self.user_errback:
                d = Deferred()
                d.addErrback(self.user_errback)
                d.errback(DefaultException(reason.getErrorMessage()))

def listen(username, room_id, callback, errback):
    auth_header = 'Basic ' + base64.b64encode("%s:%s" % (username,
        'X')).strip()

    url = 'https://streaming.campfirenow.com/room/%s/live.json' % room_id
    headers = Headers({
        'User-Agent': [USER_AGENT],
        'Authorization': [auth_header]})

    # issue the request
    agent = Agent(reactor)
    d = agent.request('GET', url, headers, None)
    d.addCallback(cbRequest, callback, errback)

    return d

def success(x):
    log.msg(x)

def failure(x):
    log.err(x)

if __name__ == '__main__':
    global campfire

    log.startLogging(sys.stdout)

    try:
        config_file = open('config.json')
        config = dict(json.loads(config_file.read()))
        users = config['users']

        # connect to Campfire
        campfire = pinder.Campfire(config['domain'], config['api_key'])
        room = campfire.find_room_by_name('BotTest')
        room.join()
        listen(campfire.me()['api_auth_token'], room.id, success, failure)
        reactor.run()
    except:
        log.err()
