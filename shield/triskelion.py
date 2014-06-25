#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import re
import simplejson

from time import time

import config


if __name__ != '__main__':
    import shield

def run(mask, func, *args, **kwargs):
    condition = re.compile(mask.replace('.', '\\.').replace('*', '.*'))
    for client in filter(lambda x: condition.match(x), shield.clients.keys()):
        getattr(shield.clients[client], func)(*args, **kwargs)

class SHIELDProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        self.name = ''
        self.authenticated = False
        self.last_received_heartbeat = False
        self.transport = transport

    def data_received(self, data):
        try:
            json = simplejson.loads(data)
        except:
            self.transport.close()
            return
        logging.debug('[LINK] >>> {0}'.format(json))
        if self.authenticated:
            if json['type'] == 'auth':
                self.writejson({'type': 'auth', 'msg': 'error', 'error': 'already-authenticated'})
            elif json['type'] == 'heartbeat':
                if json['msg'] == 'pong':
                    self.last_received_heartbeat = time()
        else:
            if json['type'] == 'auth':
                if json['fingerprint'] == config.fingerprints[json['name']]:
                    self.name = json['name']
                    self.authenticated = True
                    self.writejson({'type': 'auth', 'msg': 'authenticated'})
                    self.last_received_heartbeat = time()
                    shield.clients[self.name] = self
                    @asyncio.coroutine
                    def heartbeat():
                        while True:
                            yield from asyncio.sleep(10)
                            if not self.transport:
                                return
                            self.writejson({'type': 'heartbeat', 'msg': 'ping', 'timestamp': time()})
                            if time() - self.last_received_heartbeat > 30:
                                self.transport.close()
                                return
                    asyncio.async(heartbeat())
                else:
                    self.writejson({'type': 'auth', 'msg': 'error', 'error': 'wrong-fingerprint'})
            else:
                self.writejson({'type': json['type'], 'msg': 'error', 'error': 'not-authenticated'})

    def connection_lost(self, exc):
        logging.info('[LINK] <{0}> Connection closed'.format(self.name))
        self.transport = None
        del shield.clients[self.name]

    def writejson(self, d):
        json = simplejson.dumps(d)
        self.transport.write(json.encode('utf-8') + b'\n')
        logging.debug('[LINK] <<< {0}'.format(json))

    def exec_cmd(self, cmd):
        self.writejson({'type': 'exec', 'command': cmd})

class TriskelionIRCHandler(shield.IRCHandler):
    def on_welcome(self):
        shield.send_line('JOIN {0}'.format(config.irc_channel))

    def on_privmsg(self, nick, channel, message):
        if channel != config.irc_channel:
            return
        if message == '-update-packages-all':
            run('*', 'exec_cmd', 'apt-get update && apt-get upgrade')
        elif message == '-update-self':
            run('*', 'update_self')

handler = TriskelionIRCHandler()
def irc_handle(line):
    res = handler.on_line(line)
