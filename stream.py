import pinder
import base64
import json
import sys

from xml.sax import make_parser

from pinder.campfire import USER_AGENT

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.python import log
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted. internet.protocol import Protocol 
from xml.sax.handler import ContentHandler 

class CampfireMessageHandler(ContentHandler):

    """
    <message>
        <user-id type="integer">1424761</user-id>
        <room-id type="integer">589165</room-id>
        <created-at type="datetime">2014-03-13T18:36:50Z</created-at>
        <body>test</body>
        <type>TextMessage</type>
        <id type="integer">1223322168</id>
        <starred type="boolean">false</starred>
    </message>
    """

    def __init__(self, callback, errback):
        self.data = None
        self.user_id = None
        self.room_id = None
        self.body = None
        self.message_type = None
        self.callback = callback
        self.errback = errback

    def startElement(self, tag, attrs): 
        self.data = tag 

    def characters(self, content):
        if self.data == 'user-id':
            self.user_id = int(content)
        elif self.data == 'room-id':
            self.room_id = int(content)
        elif self.data == 'body':
            self.body = content
        elif self.data == 'type':
            self.message_type = content

    def endElement(self, name):
        if name == 'message':
            self.callback(
                    {'user_id' : self.user_id,
                     'room_id' : self.room_id, 
                     'body': self.body,
                     'type': self.message_type})

        self.data = ''

def cbRequest(response, callback, errback):
    # We should look at the response headers here and figure out what to do on error
    protocol = StreamingXMLParser(callback, errback)
    response.deliverBody(protocol)
    return protocol.done

class StreamingXMLParser(Protocol):
    def __init__(self, callback, errback):
        self.done = Deferred()
        self.callback = callback
        self.errback = errback

    def connectionMade(self):
        self._parser = make_parser()
        self._parser.setContentHandler(CampfireMessageHandler(self.callback, self.errback))

        #Feed the parser a bogus start tag, we only care about <message>
        self._parser.feed('<root>')

    def dataReceived(self, bytes):
        try:
            self._parser.feed(bytes)
        except:
            log.err()

    def connectionLost(self, reason):
        self._parser.feed('', True)
        self.done.callback(None)

def listen(username, room_id, callback, errback):
    auth_header = 'Basic ' + base64.b64encode("%s:%s" % (username,
        'X')).strip()

    url = 'https://streaming.campfirenow.com/room/%s/live.xml' % room_id
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
