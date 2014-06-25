#/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import simplejson
import subprocess
import sys
import traceback

from importlib import reload

import config


logging.basicConfig(level=logging.INFO, format='[%(asctime)s] {%(levelname)s} %(message)s')
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger().setLevel(config.loglevel)
loop = asyncio.get_event_loop()


@asyncio.coroutine
def start_agent_client():
    ev = asyncio.Event()
    while 1:
        host = config.shield_host
        port = config.shield_port
        ev.clear()
        try:
            global transport
            transport, proto = yield from loop.create_connection(protocol.AgentProtocol, host, port)
            def connection_lost(exc):
                proto._connection_lost(exc)
                ev.set()
            proto.connection_lost = connection_lost
        except Exception as e:
            logging.critical('!!! Fail to connect to server at [{0}:{1}]: {2}'.format(host, port, e))
        else:
            yield from ev.wait()
        finally:
            yield from asyncio.sleep(1)

def reload_all():
    reload(config)
    reload(protocol)
    transport.close()

def main():
    try:
        asyncio.async(start_agent_client())
        loop.run_forever()
    except KeyboardInterrupt:
        print('bye')
    finally:
        loop.close()

if __name__ == '__main__':
    sys.modules['agent'] = sys.modules['__main__']
    import protocol
    main()
