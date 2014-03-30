import argparse
import json

import pinder

from twisted.words import service

rooms = {}
irc_users = {}

config_file = open('config.json')
configuration = dict(json.loads(config_file.read()))
users = configuration['users']

parser = argparse.ArgumentParser(description='Campfire to IRC Proxy')
parser.add_argument('-d', '--debug', action='store_true')
args = parser.parse_args()

# connect to Campfire
campfire = pinder.Campfire(configuration['domain'], configuration['api_key'])
# Initialize the Cred authentication system used by the IRC server.
irc_realm = service.InMemoryWordsRealm('LuckyStrike')
