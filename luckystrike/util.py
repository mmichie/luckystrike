import config
import traceback
import re
import sys

from twisted.python import log

def campNameToString(name):
    return re.sub('\s+', '_', name).lower()

def lookupChannel(channel):
    for room_id, room in config.rooms.iteritems():
        if room['channel'] == channel:
            return room

def error(e):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    log.err(e)
    for user_name, client in config.irc_users.iteritems():
        for line in traceback.format_exception(exc_type, exc_value, exc_traceback):
            client.notice('LuckyStrike', user_name, line)
