#/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import re
import simplejson
import ssl
import subprocess
import sys
import traceback

from importlib import reload

import config


clients = {}
RE_IRCLINE = re.compile("^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)(?P<params>( +[^:][^ ]*)*)(?: +:(?P<message>.*))?$")
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] {%(levelname)s} %(message)s')
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger().setLevel(config.loglevel)
loop = asyncio.get_event_loop()


class IRCHandler(object):
    def on_welcome(self): pass
    def on_join(self, nick, channel): pass
    def on_kick(self, nick, by_nick, channel, reason): pass
    def on_part(self, nick, channel, reason): pass
    def on_quit(self, nick, channel, reason): pass
    def on_privmsg(self, nick, host, channel, message): pass

    def on_ping(self, message):
        send_line('PONG :%s' % message)

    def on_line(self, line):
        getnick = lambda x: x.split('!')[0]
        gethost = lambda x: x.split('@')[1]
        m = RE_IRCLINE.match(line)
        if m:
            prefix = m.group('prefix')
            command = m.group('command').lower()
            params = (m.group('params') or '').split() or ['']
            message = m.group('message') or ''
            if command == 'ping':
                self.on_ping(message)
            elif command == '001':
                self.on_welcome()
            elif command == 'join':
                self.on_join(getnick(prefix), message.lower())
            elif command == 'kick':
                self.on_kick(params[1], getnick(prefix), params[0].lower(), message)
            elif command == 'part':
                self.on_part(getnick(prefix), params[0].lower(), message)
            elif command == 'quit':
                self.on_quit(getnick(prefix), params[0].lower(), message)
            elif command == 'privmsg' and message == '-rehash' and gethost(prefix) == config.irc_admin_host:
                reload(config)
                reload(triskelion)
                send_line('PRIVMSG %s : All SHIELD division rehashed' % params[0])
            elif command == 'privmsg':
                self.on_privmsg(getnick(prefix), gethost(prefix), params[0].lower(), message)

@asyncio.coroutine
def start_shield_server():
    host = config.listen_host
    port = config.listen_port
    try:
        yield from loop.create_server(triskelion.SHIELDProtocol, host=host, port=port)
    except Exception as e:
        logging.critical('!!! Fail to bind server at [%s:%d]: %s' % (host, port, e.args[1]))
        return 1
    logging.info('Server bound at [%s:%d].' % (host, port))

@asyncio.coroutine
def start_irc_bot():
    while True:
        irc_reader, irc_writer = yield from asyncio.open_connection(host=config.irc_host, port=config.irc_port, **config.irc_kwargs)
        def _send_line(line):
            msg = '%s\r\n' % line
            irc_writer.write(msg.encode('utf-8'))
            logging.debug('[IRC] >>> {0}'.format(line))
        global send_line
        send_line = _send_line
        send_line('USER {0} 8 * :{0}'.format(config.irc_nick))
        send_line('NICK {0}'.format(config.irc_nick))
        while True:
            try:
                line = yield from irc_reader.readline()
                line = line.rstrip().decode('utf-8', 'ignore')
            except EOFError:
                break
            if not line:
                break
            logging.debug('[IRC] <<< {0}'.format(line))
            try:
                triskelion.irc_handle(line)
            except Exception:
                ty, exc, tb = sys.exc_info()
                send_line('PRIVMSG %s :ERROR! %s %s' % (config.irc_channel, ty, exc))
                traceback.print_exception(ty, exc, tb)
        yield from asyncio.sleep(10)

def main():
    try:
        asyncio.async(start_shield_server())
        asyncio.async(start_irc_bot())
        loop.run_forever()
    except KeyboardInterrupt:
        print('bye')
    finally:
        loop.close()

if __name__ == '__main__':
    sys.modules['shield'] = sys.modules['__main__']
    import triskelion
    main()
