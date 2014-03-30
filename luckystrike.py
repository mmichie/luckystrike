#!/usr/bin/env python
# coding=utf-8

import sys
import os

from twisted.conch import manhole, manhole_ssh
from twisted.cred import checkers, portal
from twisted.internet import reactor, ssl
from twisted.python import log
from twisted.words import service

from luckystrike import util
from luckystrike import config
from luckystrike.user import LuckyStrikeIRCFactory

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

    log.startLogging(sys.stdout)

    try:

        for room in config.campfire.rooms():
            config.rooms[room['id']] = room
            config.rooms[room['id']]['channel'] = util.campNameToString(room['name'])
            config.rooms[room['id']]['stream'] = None
            config.rooms[room['id']]['streaming'] = False

            log.msg('Adding %s to IRC as %s' % (room['name'],
                config.rooms[room['id']]['channel']))

            config.irc_realm.addGroup(service.Group(config.rooms[room['id']]['channel']))

        user_db = checkers.InMemoryUsernamePasswordDatabaseDontUse(**config.users)
        irc_portal = portal.Portal(config.irc_realm, [user_db])

        # Start IRC and Manhole
        reactor.listenTCP(6667, LuckyStrikeIRCFactory(config.irc_realm, irc_portal))

        if config.args.debug:
            reactor.listenTCP(2222, getManholeFactory(globals(), admin='aaa'))

        if (
                os.path.exists(config.configuration.get('ssl_crt', '')) and
                os.path.exists(config.configuration.get('ssl_key', ''))):
            reactor.listenSSL(6697,
                              LuckyStrikeIRCFactory(config.irc_realm, irc_portal),
                              ssl.DefaultOpenSSLContextFactory(
                                config.configuration['ssl_key'], config.configuration['ssl_crt']))

        reactor.run()
    except:
        log.err()
