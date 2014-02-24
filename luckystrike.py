import json
import re
import sys

import pinder

from twisted.conch import manhole, manhole_ssh
from twisted.cred import checkers, portal
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.words import service
from twisted.words.protocols import irc

users = dict(mmichie='pass1', admin='admin')
rooms = {}
irc_users = {}

class LuckyStrikeIRCUser(service.IRCUser):

    """
    Override Twisted's IRC USer

    Note: consider overriding irc_NICK to prevent nickserv password prompt
    """
    def connectionMade(self):
        service.IRCUser.connectionMade(self)
        log.msg('User connected from %s' % self.hostname)

    def _cbLogin(self, (iface, avatar, logout)):
        service.IRCUser._cbLogin(self, (iface, avatar, logout))
        log.msg('User authenticated as: %s' % self.avatar.name)
        irc_users[self.avatar.name] = self

    def connectionLost(self, reason):
        log.msg('User disconnected')
        service.IRCUser.connectionLost(self, reason)
        del irc_users[self.avatar.name]

    def irc_JOIN(self, prefix, params):
        service.IRCUser.irc_JOIN(self, prefix, params)
        log.msg('Joined channel: %s, %s' % (prefix, params))

        # Join Campfire room
        room_info = lookupChannel(params[0].strip('#'))
        log.msg('Starting to stream: %s' % room_info['name'])
        room = campfire.find_room_by_name(room_info['name'])
        room.join()
        
        if 'streaming' not in rooms[room.id]:
            rooms[room.id]['streaming'] = True
            room.listen(incoming, error, start_reactor=False)

    def privmsg(self, sender, recip, message):
        service.IRCUser.privmsg(self, sender, recip, message)
        log.msg('Got sent a privmsg: %s, %s, %s' % (sender, recip, message))

    def irc_PART(self, prefix, params):
        service.IRCUser.irc_PART(self, prefix, params)
        log.msg('Left channel: %s, %s' % (prefix, params))

        # Leave Campfire room
        room_info = lookupChannel(params[0].strip('#'))
        log.msg('Stopping stream to : %s' % room_info['name'])
        room = campfire.find_room_by_name(room_info['name'])
        room.leave()
        #rooms[room.id]['streaming'] = False

class LuckyStrikeIRCFactory(service.IRCFactory):
    protocol = LuckyStrikeIRCUser

def campNameToString(name):
    return re.sub('\s+', '_', name).lower()

def lookupChannel(channel):
    for room_id, room in rooms.iteritems():
        if room['channel'] == channel:
            return room

def write_message(message, user, channel):
    for user_name, client in irc_users.iteritems():
        client.privmsg(user, '#%s' % channel, message)
        log.msg('Writing to %s on %s: %s' % (user_name, channel, message))

def incoming(message):
    log.msg(message)

    if message['user_id'] is not None:
        user = campfire.user(message['user_id'])['user']
    else:
        user = None

    if message['type'] == 'TextMessage':
        write_message(message['body'], campNameToString(user['name']), rooms[message['room_id']]['channel'])
    if message['type'] == 'KickMessage':
        write_message('%s has left' % user['name'], campNameToString(user['name']), rooms[message['room_id']]['channel'])
    if message['type'] == 'EnterMessage':
        write_message('%s has joined' % user['name'], campNameToString(user['name']), rooms[message['room_id']]['channel'])

def error(e):
    log.err(e)

def getManholeFactory(namespace, **passwords):
    realm = manhole_ssh.TerminalRealm()

    def getManhole(_):
        return manhole.Manhole(namespace)

    realm.chainedProtocolFactory.protocolFactory = getManhole
    p = portal.Portal(realm)
    p.registerChecker(checkers.InMemoryUsernamePasswordDatabaseDontUse(**passwords))
    f = manhole_ssh.ConchFactory(p)

    return f

if __name__ == '__main__':
    global campfire

    log.startLogging(sys.stdout)

    try:
        config_file = open('config.json')
        config = dict(json.loads(config_file.read()))

        # connect to Campfire
        campfire = pinder.Campfire(config['domain'], config['api_key']) 

        # Initialize the Cred authentication system used by the IRC server.
        irc_realm = service.InMemoryWordsRealm('LuckyStrike')
        for room in campfire.rooms():
            rooms[room['id']] = room
            rooms[room['id']]['channel'] = campNameToString(room['name'])
            log.msg('Adding %s to IRC as %s' % (room['name'], rooms[room['id']]['channel']))
            irc_realm.addGroup(service.Group(rooms[room['id']]['channel']))

        user_db = checkers.InMemoryUsernamePasswordDatabaseDontUse(**users)
        irc_portal = portal.Portal(irc_realm, [user_db])

        # Start IRC and Manhole
        reactor.listenTCP(6667, LuckyStrikeIRCFactory(irc_realm, irc_portal))
        reactor.listenTCP(2222, getManholeFactory(globals(), admin='aaa'))

        reactor.run()
    except:
        log.err()
