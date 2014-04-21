import re

from twisted.internet import defer
from twisted.python import log
from twisted.words import service
from twisted.words.protocols import irc

from luckystrike import util
from luckystrike import stream
from luckystrike import config
from luckystrike import route

def replace_usernames(room, message):
    """
    Search message for potential usernames, return message with expanded name
    """
    users = {}
    replace = []

    #consider caching this, but if we error out, just don't worry about
    #replacing usernames
    try:
        for user in room._get()['room']['users']:
            users[util.campNameToString(user['name'])] = user['name']
    except:
        log.err()
        return message

    # find all words that match usernames
    for m in message.split():
        a = [(k, v) for (k, v) in users.iteritems() if re.sub(r'\W+', '', m) == k]
        for i in a:
            replace.append(i)

    # search and replace all irc to campfire names
    if len(replace) > 0:
        log.msg('Found usernames to replace in message :%s' % replace)
        message_replacement = message
        for r in replace:
            p = re.compile(r[0])
            message_replacement = p.sub(r[1], message_replacement)

        log.msg('Transforming %s into: %s' % (message, message_replacement))

        return message_replacement
    else:
        return message

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
        room_info = util.channel_to_room(channel.strip('#'))
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
        #[(u'mmichie', 'LuckyStrike', 'LuckyStrike', u'mmichie', 'H', 0, u'mmichie')]
        log.msg('who called: %s, %s, %s' % (user, channel, memberInfo))
        room = self.channelToRoom(channel)

        users = room._get()['room']['users']
        for camp_user in users:
            name = util.campNameToString(camp_user['name'])
            memberInfo.append((name, 'LuckyStrike', 'LuckyStrike', name, 'H', 0, name))

        service.IRCUser.who(self, user, channel, memberInfo)

    def irc_JOIN(self, prefix, params):
        for channel in params[0].split(','):
            room_info = util.channel_to_room(channel.strip('#'))
            group = config.irc_realm.groups[util.campNameToString(room_info['name'])]
            group.setMetadata({'topic': room_info['topic']})

            service.IRCUser.irc_JOIN(self, prefix, [channel])
            log.msg('Joined channel: %s, %s' % (prefix, channel))

            # Join Campfire room
            log.msg('Starting to stream: %s' % room_info['name'])
            room = config.campfire.find_room_by_name(room_info['name'])
            room.join()

            if config.rooms[room.id]['stream'] is None:
                username, password = room._connector.get_credentials()
                config.rooms[room.id]['stream'] = stream.listen(username, room.id,
                    route.route_incoming_message, util.error)

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
            message = replace_usernames(room, params[1])

            # Handle /me
            if message.startswith('\x01ACTION'):
                before = message
                message = message.strip('\x01')
                message = '*' + ' '.join(message.split()[1:]) + '*'
                log.msg('ACTION Translated from %s to %s' % (before, message))

            log.msg('Speaking to %s: %s' % (room.name, message.decode('ascii', 'ignore')))
            try:
                room.speak(message)
            except Exception as exception:
                util.error(exception)

    def irc_PART(self, prefix, params):
        service.IRCUser.irc_PART(self, prefix, params)
        log.msg('Left channel: %s, %s' % (prefix, params))

        # Leave Campfire room
        room_info = util.channel_to_room(params[0].strip('#'))
        log.msg('Stopping stream to : %s' % room_info['name'])
        room = config.campfire.find_room_by_name(room_info['name'])
        room.leave()
        try:
            factory, connection = config.rooms[room.id]['stream']
            factory.stopTrying()
            connection.disconnect()
            config.rooms[room.id]['stream'] = None
        except:
            log.err()

    def irc_ISON(self, prefix, params):
        pass

    def irc_CAP(self, prefix, params):
        pass

    def irc_AWAY(self, prefix, params):
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
