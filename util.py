import re
import config

def campNameToString(name):
    return re.sub('\s+', '_', name).lower()

def lookupChannel(channel):
    for room_id, room in config.rooms.iteritems():
        if room['channel'] == channel:
            return room

