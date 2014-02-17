import sys
import json
import pyfire

from twisted.manhole import telnet
from twisted.cred import checkers, portal
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.python import log
from twisted.words import service
from twisted.conch import manhole, manhole_ssh

def incoming(message):
    #ircfactory.protocol.privmsg('mmichie', 'hi')
    #ircfactory.protocol.notice('username!ident@hostmask', 'username!ident@hostmask', 'hi')
    ircfactory.protocol.privmsg('username!ident@hostmask', 'username!ident@hostmask', 'hi')
    user = ''
    room = None
    if message.user:
        user = message.user.name
    if message.room:
        room = message.room
        #print dir(room)
    #print dir(message)

    if message.is_joining():
        print '--> %s ENTERS THE ROOM: %s' % (user, room)
    elif message.is_leaving():
        print '<-- %s LEFT THE ROOM: %s ' % (user, room)
    elif message.is_tweet():
        print '[%s] %s TWEETED "%s" - %s' % (user, message.tweet['user'],
            message.tweet['tweet'], message.tweet['url'])
    elif message.is_text():
        print '%s: [%s] %s' % (room, user, message.body)
    elif message.is_upload():
        print '-- %s UPLOADED FILE %s: %s' % (user, message.upload['name'],
            message.upload['url'])
    elif message.is_topic_change():
        print '-- %s CHANGED TOPIC TO "%s"' % (user, message.body)

def error(e):
    print('Stream STOPPED due to ERROR: %s' % e)
    print('Press ENTER to continue')

ROOM = 'bot'
USERS = dict( mmichie='pass1',admin='admin')

def getManholeFactory(namespace, **passwords):
    realm = manhole_ssh.TerminalRealm()
    def getManhole(_): return manhole.Manhole(namespace)
    realm.chainedProtocolFactory.protocolFactory = getManhole
    p = portal.Portal(realm)
    p.registerChecker(
        checkers.InMemoryUsernamePasswordDatabaseDontUse(**passwords))
    f = manhole_ssh.ConchFactory(p)
    return f

if __name__ == '__main__':
    global ircfactory

    log.startLogging(sys.stdout)

    try:
        config_file = open('config.json')
        config = dict(json.loads(config_file.read()))
        # Initialize the Cred authentication system used by the IRC server.
        realm = service.InMemoryWordsRealm('ProxyRealm')
        realm.addGroup(service.Group(ROOM))
        #print dir(realm)
        user_db = checkers.InMemoryUsernamePasswordDatabaseDontUse(**USERS)
        irc_portal = portal.Portal(realm, [user_db])

        # connect to Campfire
        campfire = pyfire.Campfire(config['domain'], config['e-mail'], config['password'], ssl=True)
        connection = campfire.get_connection()
        reactor = connection.get_twisted_reactor()

        # Join Campfire room
        room = campfire.get_room_by_name('BotTest')
        room.join()
        stream = room.get_stream(error_callback=error)

        # Startup IRC Server
        ircfactory = service.IRCFactory(realm, irc_portal)
        endpoint = TCP4ServerEndpoint(reactor, 6667)
        endpoint.listen(ircfactory)

        reactor.listenTCP(2222, getManholeFactory(globals(), admin='aaa'))

        # Start Campfire stream
        stream.attach(incoming).start()
    except:
        log.err()
        #stream.stop().join()
        #room.leave()
