#!/usr/bin/env python
# coding=utf-8

import base64
import json
import re
import sys

import pinder
from pinder.campfire import USER_AGENT
from pinder import streaming

from twisted.conch import manhole, manhole_ssh
from twisted.cred import checkers, portal
from twisted.internet import reactor, ssl
from twisted.internet import task
from twisted.internet.defer import Deferred
from twisted.python import log
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.words import service
from twisted.words.protocols import irc

rooms = {}
irc_users = {}

def _get_response(response, callback, errback):
    response.deliverBody(streaming.StreamingParser(callback, errback))
    return Deferred()

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

    def channelToRoom(self, channel):
        room_info = lookupChannel(channel.strip('#'))
        room = campfire.find_room_by_name(room_info['name'])

        return room

    def connectionLost(self, reason):
        log.msg('User disconnected: %s', reason)
        if self.avatar is not None:
            del irc_users[self.avatar.name]
        service.IRCUser.connectionLost(self, reason)

    def names(self, user, channel, names):
        log.msg('names called: %s, %s, %s' % (user, channel, names))

        room = self.channelToRoom(channel)

        names = []
        users = room._get()['room']['users']
        for camp_user in users:
            names.append(campNameToString(camp_user['name']))

        service.IRCUser.names(self, user, channel, names)

    def who(self, user, channel, memberInfo):
        log.msg('who called: %s, %s, %s' % (user, channel, memberInfo))

    def irc_JOIN(self, prefix, params):
        for channel in params[0].split(','):
            service.IRCUser.irc_JOIN(self, prefix, [channel])
            log.msg('Joined channel: %s, %s' % (prefix, channel))
            # Join Campfire room
            room_info = lookupChannel(channel.strip('#'))
            log.msg('Starting to stream: %s' % room_info['name'])
            room = campfire.find_room_by_name(room_info['name'])
            room.join()
            rooms[room.id]['streaming'] = True

            if rooms[room.id]['stream'] is None:
                username, password = room._connector.get_credentials()
                rooms[room.id]['stream'] = self.listen(username, password, room.id, incoming, error)

    def irc_PRIVMSG(self, prefix, params):
        log.msg('privmsg called: !%s!, %s' % (prefix, params))
        service.IRCUser.irc_PRIVMSG(self, prefix, params)
        if params[0].startswith('#'):
            room = self.channelToRoom(params[0])
            room.speak(params[1])

    def listen(self, username, password, room_id, callback, errback):
        auth_header = 'Basic ' + base64.b64encode("%s:%s" % (username, password)).strip()
        url = 'https://streaming.campfirenow.com/room/%s/live.json' % room_id
        headers = Headers({
            'User-Agent': [USER_AGENT],
            'Authorization': [auth_header]})

        # issue the request
        agent = Agent(reactor)
        d = agent.request('GET', url, headers, None)
        d.addCallback(_get_response, callback, errback)

        return d

    def receive(self, sender, recipient, message):
        log.msg('Receive: %s' % message)
        service.IRCUser.receive(self, sender, recipient, message)

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
        try:
            # This doesn't seem to do what we want yet, need to figure out how to
            # actually cut off the stream
            rooms[room.id]['stream'].pause()
            rooms[room.id]['stream'].cancel()
            rooms[room.id]['streaming'] = False
        except:
            log.err()

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

    if not rooms[message['room_id']]['streaming']:
        log.msg('Should not be streaming this room, ignoring!')
        return

    if message['user_id'] is not None:
        user = campfire.user(message['user_id'])['user']
    else:
        user = None

    # Don't write messages that I've sent, or that aren't Text
    if message['type'] == 'TextMessage' and campfire.me()['id'] != message['user_id']:
        write_message(message['body'], campNameToString(user['name']), rooms[message['room_id']]['channel'])

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
        users = config['users']

        # connect to Campfire
        campfire = pinder.Campfire(config['domain'], config['api_key']) 
        print campfire.me()
        # Initialize the Cred authentication system used by the IRC server.
        irc_realm = service.InMemoryWordsRealm('LuckyStrike')
        for room in campfire.rooms():
            rooms[room['id']] = room
            rooms[room['id']]['channel'] = campNameToString(room['name'])
            rooms[room['id']]['stream'] = None
            rooms[room['id']]['streaming'] = False

            log.msg('Adding %s to IRC as %s' % (room['name'], rooms[room['id']]['channel']))
            irc_realm.addGroup(service.Group(rooms[room['id']]['channel']))

        user_db = checkers.InMemoryUsernamePasswordDatabaseDontUse(**users)
        irc_portal = portal.Portal(irc_realm, [user_db])

        # Start IRC and Manhole
        reactor.listenTCP(6667, LuckyStrikeIRCFactory(irc_realm, irc_portal))
        reactor.listenTCP(2222, getManholeFactory(globals(), admin='aaa'))
        reactor.listenSSL(6697, LuckyStrikeIRCFactory(irc_realm, irc_portal),
                          ssl.DefaultOpenSSLContextFactory(
                            'keys/server.key', 'keys/server.crt'))

        reactor.run()
    except:
        log.err()
