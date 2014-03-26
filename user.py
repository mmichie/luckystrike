from twisted.internet import defer
from twisted.python import log
from twisted.words import service
from twisted.words.protocols import irc

import util
import stream
import config
import route

class LuckyStrikeIRCUser(service.IRCUser):

    """
    Override Twisted's IRC User
    """

    def connectionMade(self):
        service.IRCUser.connectionMade(self)
        log.msg('User connected from %s' % self.hostname)

    def _cbLogin(self, (iface, avatar, logout)):
        service.IRCUser._cbLogin(self, (iface, avatar, logout))
        log.msg('User authenticated as: %s' % self.avatar.name)
        config.irc_users[self.avatar.name] = self

    def channelToRoom(self, channel):
        room_info = util.lookupChannel(channel.strip('#'))
        room = config.campfire.find_room_by_name(room_info['name'])

        return room

    def connectionLost(self, reason):
        log.msg('User disconnected: %s', reason)
        if self.avatar is not None:
            del config.irc_users[self.avatar.name]
        service.IRCUser.connectionLost(self, reason)

    def names(self, user, channel, names):
        log.msg('names called: %s, %s, %s' % (user, channel, names))

        room = self.channelToRoom(channel)

        names = []
        users = room._get()['room']['users']
        for camp_user in users:
            names.append(util.campNameToString(camp_user['name']))

        service.IRCUser.names(self, user, channel, names)

    def who(self, user, channel, memberInfo):
        log.msg('who called: %s, %s, %s' % (user, channel, memberInfo))

    def irc_JOIN(self, prefix, params):
        for channel in params[0].split(','):
            room_info = util.lookupChannel(channel.strip('#'))
            group = config.irc_realm.groups[util.campNameToString(room_info['name'])]
            group.setMetadata({'topic': room_info['topic']})

            service.IRCUser.irc_JOIN(self, prefix, [channel])
            log.msg('Joined channel: %s, %s' % (prefix, channel))

            # Join Campfire room
            log.msg('Starting to stream: %s' % room_info['name'])
            room = config.campfire.find_room_by_name(room_info['name'])
            room.join()
            config.rooms[room.id]['streaming'] = True

            if config.rooms[room.id]['stream'] is None:
                username, password = room._connector.get_credentials()
                config.rooms[room.id]['stream'] = stream.listen(username, room.id,
                    route.route_incoming_message, route.error)

    def irc_TOPIC(self, prefix, params):
        service.IRCUser.irc_TOPIC(self, prefix, params)
        channel = params[0].strip('#')
        topic = params[1]
        room = self.channelToRoom(channel)
        log.msg('Setting topic: %s on %s' % (room.name, topic))
        room.update(room.name, topic)

    def irc_PRIVMSG(self, prefix, params):
        service.IRCUser.irc_PRIVMSG(self, prefix, params)
        if params[0].startswith('#'):
            room = self.channelToRoom(params[0])
            room.speak(params[1])
            log.msg('Speaking to %s: %s' % (room.name, params[1].decode('ascii', 'ignore')))

    def irc_PART(self, prefix, params):
        service.IRCUser.irc_PART(self, prefix, params)
        log.msg('Left channel: %s, %s' % (prefix, params))

        # Leave Campfire room
        room_info = util.lookupChannel(params[0].strip('#'))
        log.msg('Stopping stream to : %s' % room_info['name'])
        room = config.campfire.find_room_by_name(room_info['name'])
        room.leave()
        try:
            # This doesn't seem to do what we want yet, need to figure out how
            # to actually cut off the stream
            config.rooms[room.id]['stream'].pause()
            config.rooms[room.id]['stream'].cancel()
            config.rooms[room.id]['streaming'] = False
        except:
            log.err()

    def irc_ISON(self, prefix, params):
        pass

    def irc_CAP(self, prefix, params):
        pass

    def irc_LIST(self, prefix, params):
        """List query

        Return information about the indicated channels, or about all
        channels if none are specified.

        Parameters: [ <channel> *( "," <channel> ) [ <target> ] ]
        """
        #<< list #python
        #>> :orwell.freenode.net 321 exarkun Channel :Users  Name
        #>> :orwell.freenode.net 322 exarkun #python 358 :The Python programming language
        #>> :orwell.freenode.net 323 exarkun :End of /LIST
        if params:
            # Return information about indicated channels
            try:
                channels = params[0].decode(self.encoding).split(',')
            except UnicodeDecodeError:
                self.sendMessage(
                    irc.ERR_NOSUCHCHANNEL, params[0],
                    ":No such channel (could not decode your unicode!)")
                return

            groups = []
            for ch in channels:
                if ch.startswith('#'):
                    ch = ch[1:]
                groups.append(self.realm.lookupGroup(ch))

            groups = defer.DeferredList(groups, consumeErrors=True)
            groups.addCallback(lambda gs: [r for (s, r) in gs if s])
        else:
            # Return information about all channels
            groups = self.realm.itergroups()

        def cbGroups(groups):
            def gotSize(size, group):
                return '#'+group.name, size, group.meta.get('topic')
            d = defer.DeferredList([
                group.size().addCallback(gotSize, group) for group in groups])
            d.addCallback(lambda results: self.list([r for (s, r) in results if s]))
            return d
        groups.addCallback(cbGroups)

class LuckyStrikeIRCFactory(service.IRCFactory):
    protocol = LuckyStrikeIRCUser

