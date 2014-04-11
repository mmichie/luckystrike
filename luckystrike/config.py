import argparse
import json
from os import path

import pinder

from twisted.words import service

rooms = {}
irc_users = {}

if path.exists(path.expanduser('~') + '/.luckystrike/config.json'):
    with open(path.expanduser('~') + '/.luckystrike/config.json') as config_file:
        configuration = dict(json.loads(config_file.read()))
else:
    with open('config.json') as config_file:
        configuration = dict(json.loads(config_file.read()))

users = configuration['users']

parser = argparse.ArgumentParser(description='Campfire to IRC Proxy')
parser.add_argument(
        '-d', '--debug', 
        action='store_true', 
        help='increase debug level'
)
parser.add_argument(
        '-s', '--setup_config', 
        action='store_true', 
        help='generate config.json'
)
args = parser.parse_args()

# connect to Campfire
campfire = pinder.Campfire(configuration['domain'], configuration['api_key'])
# Initialize the Cred authentication system used by the IRC server.
irc_realm = service.InMemoryWordsRealm('LuckyStrike')
