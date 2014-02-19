import sys
import json
import pyfire
import re

from twisted.internet import task
from twisted.cred import checkers, portal
from twisted.python import log
from twisted.words import service
from twisted.conch import manhole, manhole_ssh

from multiprocessing import Queue

ROOM = 'bot'
USERS = dict(mmichie='pass1', admin='admin')

q = Queue()
irc_users = []

def pollQueue():
    if q.empty():
        return
    else:
        (user, room, message) = q.get(block=False)
        processMessage(user, room, message)

def processMessage(user, room, message):

    try:
        log.msg('Writing messages')
        if len(irc_users) > 0 or len(message) == 0:
            irc = irc_users[0]
            irc.privmsg(user, '#bot', message)
        else:
            log.msg('No users on IRC server to write, or blank message!')
    except:
        log.err()

class LuckyStrikeIRCUser(service.IRCUser):

    """
    Override Twisted's IRC USer

    Note: consider overriding irc_NICK to prevent nickserv password prompt
    """
    def connectionMade(self):
        global irc_users

        self.irc_PRIVMSG = self.irc_NICKSERV_PRIVMSG
        self.realm = self.factory.realm
        self.hostname = self.realm.name
        log.msg('User connected from %s' % self.hostname)
        irc_users.append(self)
        log.msg('!!%s: %s!!' % (id(irc_users), irc_users))

class LuckyStrikeIRCFactory(service.IRCFactory):
    protocol = LuckyStrikeIRCUser

def campNameToString(name):
    return re.sub('\s+', '_', name).lower()

def incoming(message):
    user = ''
    msg = ''
    room = None
    if message.user:
        user = campNameToString(message.user.name)
    if message.room:
        room = campNameToString(str(message.room))

    if message.is_joining():
        msg = '--> %s ENTERS THE ROOM: %s' % (user, room)
    elif message.is_leaving():
        msg = '<-- %s LEFT THE ROOM: %s ' % (user, room)
    elif message.is_tweet():
        msg = '[%s] %s TWEETED "%s" - %s' % (user, message.tweet['user'],
            message.tweet['tweet'], message.tweet['url'])
    elif message.is_text():
        msg = message.body
    elif message.is_upload():
        msg = '-- %s UPLOADED FILE %s: %s' % (user, message.upload['name'],
            message.upload['url'])
    elif message.is_topic_change():
        msg = '-- %s CHANGED TOPIC TO "%s"' % (user, message.body)

    q.put((user, room, msg))

def error(e):
    print('Stream STOPPED due to ERROR: %s' % e)
    print('Press ENTER to continue')

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
    global twisted_reactor
    log.startLogging(sys.stdout)

    try:
        config_file = open('config.json')
        config = dict(json.loads(config_file.read()))
        # Initialize the Cred authentication system used by the IRC server.
        realm = service.InMemoryWordsRealm('ProxyRealm')
        realm.addGroup(service.Group(ROOM))
        user_db = checkers.InMemoryUsernamePasswordDatabaseDontUse(**USERS)
        irc_portal = portal.Portal(realm, [user_db])

        # connect to Campfire
        campfire = pyfire.Campfire(config['domain'], config['e-mail'], config['password'], ssl=True)
        connection = campfire.get_connection()
        twisted_reactor = connection.get_twisted_reactor()

        # Start IRC and Manhole
        twisted_reactor.listenTCP(6667, LuckyStrikeIRCFactory(realm, irc_portal))
        twisted_reactor.listenTCP(2222, getManholeFactory(globals(), admin='aaa'))

        l = task.LoopingCall(pollQueue)
        l.start(0.1)

        # Join Campfire room
        room = campfire.get_room_by_name('BotTest')
        room.join()
        stream = pyfire.stream.Stream(room, error_callback=error)

        # Start Campfire stream
        stream.attach(incoming).start()
    except:
        log.err()
        #stream.stop().join()
        #room.leave()
