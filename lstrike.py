#!/usr/bin/env python
# coding=utf-8

import json
import os
import sys

from collections import defaultdict

from twisted.conch import manhole, manhole_ssh
from twisted.cred import checkers, portal
from twisted.internet import reactor, ssl
from twisted.internet import task
from twisted.python import log
from twisted.words import service

from luckystrike import util
from luckystrike import config
from luckystrike.user import LuckyStrikeIRCFactory

def setup_config():
    """
    Easier walkthrough for user to setup .luckystrike/config
    """
    print 'Please input domain, without tld, for example.com, input example'
    domain = raw_input('Domain: ')
    user = raw_input('IRC nickname: ')
    password = util.generate_password()
    api_key = raw_input('Campfire API key: ')

    d = defaultdict()
    d['domain'] = domain
    d['users'] = {user : password}
    d['api_key'] = api_key

    print 'Your username:%s, and password: %s' % (user, password)

    directory = os.path.expanduser('~') + '/.luckystrike'
    if not os.path.exists(directory):
        os.makedirs(directory)

    print 'Writing config to %sconfig.json' % directory

    with open(directory + '/config.json', 'w') as config_file:
        json.dump(d, config_file)

def getManholeFactory(namespace, **passwords):
    """
    Return a Manhole SSH factory for debug purposes
    """
    realm = manhole_ssh.TerminalRealm()

    def getManhole(_):
        return manhole.Manhole(namespace)

    realm.chainedProtocolFactory.protocolFactory = getManhole
    p = portal.Portal(realm)
    p.registerChecker(checkers.InMemoryUsernamePasswordDatabaseDontUse(**passwords))
    f = manhole_ssh.ConchFactory(p)

    return f

def watchdog():
    """
    Track last message received per room, call periodically in a reactor loop
    """
    for room in config.rooms.itervalues():
        if room['streaming']:
            log.msg('Last timestamp from %s is %s' % (room['channel'],
                room['heartbeat']))

if __name__ == '__main__':
    if config.args.setup_config:
        setup_config()
        sys.exit(0)

    log.startLogging(sys.stdout)

    try:
        # Store pid file first thing
        pidfile = config.configuration.get('pidfile', None)
        if pidfile is not None:
            with open(pidfile, 'w+') as pf:
                pf.write("%s\n" % str(os.getpid()))

        for room in config.campfire.rooms():
            config.rooms[room['id']] = room
            config.rooms[room['id']]['channel'] = util.campNameToString(room['name'])
            config.rooms[room['id']]['stream'] = None
            config.rooms[room['id']]['streaming'] = False
            config.rooms[room['id']]['heartbeat'] = None

            log.msg('Adding %s to IRC as %s' % (room['name'],
                config.rooms[room['id']]['channel']))

            config.irc_realm.addGroup(service.Group(config.rooms[room['id']]['channel']))

        user_db = checkers.InMemoryUsernamePasswordDatabaseDontUse(**config.users)
        irc_portal = portal.Portal(config.irc_realm, [user_db])

        # Start IRC and Manhole
        reactor.listenTCP(int(config.configuration.get('port', 6667)),
                LuckyStrikeIRCFactory(config.irc_realm, irc_portal))

        if config.args.debug:
            admin_password = util.generate_password()
            log.msg('Staring ManHole with admin password: %s' % admin_password)
            reactor.listenTCP(
                    int(config.configuration.get('manhole_port', 2222)),
                    getManholeFactory(globals(), admin=admin_password),
                    interface='127.0.0.1'
            )

        if (os.path.exists(config.configuration.get('ssl_crt', '')) and
            os.path.exists(config.configuration.get('ssl_key', ''))):

            reactor.listenSSL(int(config.configuration.get('ssl_port', 6697)),
                    LuckyStrikeIRCFactory(config.irc_realm, irc_portal),
                    ssl.DefaultOpenSSLContextFactory(
                        config.configuration['ssl_key'],
                        config.configuration['ssl_crt'])
                    )

        if config.args.debug:
            t = task.LoopingCall(watchdog)
            t.start(240)

        reactor.run()

    except:
        log.err()
    finally:
        if pidfile is not None:
            os.unlink(pidfile)
