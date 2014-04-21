import config
import util

from datetime import datetime
from twisted.python import log

def write_message(message, user, channel):
    for user_name, client in config.irc_users.iteritems():
        #assume *messages* are ACTION and translate accordingly
        if message.startswith('*') and message.endswith('*'):
            # I don't get why client.action doesn't do this in Twisted - mim
            client.privmsg(user, '#%s' % channel, '\x01ACTION %s\x01' % message.strip('*'))
            log.msg('Translating action to %s on %s: %s' % (user_name, channel, message.encode('ascii', 'ignore')))
        else:
            client.privmsg(user, '#%s' % channel, message)
            log.msg('Writing to %s on %s: %s' % (user_name, channel, message.encode('ascii', 'ignore')))

def write_part_message(user, channel, reason=None):
    for user_name, client in config.irc_users.iteritems():
        client.part('%s!campfire@luckystrike' % user, channel, reason)

def write_join_message(user, channel):
    for user_name, client in config.irc_users.iteritems():
        client.join('%s!campfire@luckystrike' % user, channel)

def route_incoming_message(message):
    """
    Take incoming message from Campfire, sort by type and deliver to IRC
    """
    if message['user_id'] is not None:
        user = config.campfire.user(message['user_id'])['user']
    else:
        user = None

    channel = '#' + config.rooms[message['room_id']]['channel']

    # Update last message seen
    config.rooms[message['room_id']]['heartbeat'] = datetime.utcnow()

    # Don't write messages that I've sent, or that aren't Text
    if message['type'] == 'TextMessage' and config.campfire.me()['id'] != message['user_id']:
        write_message(message['body'], util.campNameToString(user['name']),
                config.rooms[message['room_id']]['channel'])
    elif message['type'] == 'EnterMessage':
        log.msg('EnterMessage %s joined %s' % (message['user_id'], message['room_id']))
        nick = util.campNameToString(config.campfire.user(message['user_id'])['user']['name'])
        write_join_message(nick, channel)
    elif message['type'] == 'KickMessage':
        log.msg('KickMessage %s left %s' % (message['user_id'], message['room_id']))
        nick = util.campNameToString(config.campfire.user(message['user_id'])['user']['name'])
        write_part_message(nick, channel, 'Timed out')
    elif message['type'] == 'LeaveMessage':
        log.msg('LeaveMessage %s left %s' % (message['user_id'], message['room_id']))
        nick = util.campNameToString(config.campfire.user(message['user_id'])['user']['name'])
        write_part_message(nick, channel, 'Left channel')
    elif message['type'] == 'PasteMessage':
        # Write first 5 lines of paste
        write_message('Paste: https://%s.campfirenow.com/room/%s/paste/%s' % (config.configuration['domain'], message['room_id'], message['id']), util.campNameToString(user['name']), config.rooms[message['room_id']]['channel'])
        lines = message['body'].splitlines()
        for line in lines[:5]:
            write_message(line, util.campNameToString(user['name']), config.rooms[message['room_id']]['channel'])
        if len(lines) > 5:
            write_message('... Paste too long ...', util.campNameToString(user['name']), config.rooms[message['room_id']]['channel'])
    elif message['type'] == 'SoundMessage':
        write_message('Played a sound: %s' % message['body'], util.campNameToString(user['name']), config.rooms[message['room_id']]['channel'])
        log.msg('SoundMessage: %s' % message['body'])
    elif message['type'] == 'TweetMessage':
        write_message(message['body'], util.campNameToString(user['name']), config.rooms[message['room_id']]['channel'])
    elif message['type'] == 'TimestampMessage':
        config.rooms[message['room_id']]['heartbeat'] =  datetime.strptime(
                message['created_at'][:-6], '%Y/%m/%d %H:%M:%S') 
        if config.args.debug:
            log.msg('Timestamp received: %s' % message['created_at'])
    elif message['type'] == 'UploadMessage':
        write_message('Uploaded: https://%s.campfirenow.com/room/%s/uploads/%s' % (config.configuration['domain'], message['room_id'], message['body']), util.campNameToString(user['name']), config.rooms[message['room_id']]['channel'])
        log.msg('UploadMessage: %s' % message['body'])
    elif message['type'] == 'TopicChangeMessage':
        log.msg('TopicChangeMessage: %s' % message['body'])
        group = config.irc_realm.groups[config.rooms[message['room_id']]['channel']]
        group.setMetadata({'topic': message['body']})
    elif message['type'] == 'AllowGuestsMessage':
        write_message('Has allowed Guests', util.campNameToString(user['name']), config.rooms[message['room_id']]['channel'])
        log.msg('AllowGuestsMessage: %s' % message['body'])
    elif message['type'] == 'DisallowGuestsMessage':
        write_message('Has Disallowed Guests', util.campNameToString(user['name']), config.rooms[message['room_id']]['channel'])
        log.msg('DisallowGuestsMessage: %s' % message['body'])
    elif config.campfire.me()['id'] != message['user_id']:
        log.err('Unknown message type received: %s' % message)
