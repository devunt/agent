#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import asyncio
import logging
import psutil
import simplejson
import subprocess

from time import time

import config


def loadavg():
    with open('/proc/loadavg', 'r') as f:
        load = f.read().split()[0]
    return load

def memory():
    return psutil.virtual_memory().percent

def disk():
    return ', '.join(
        map(
            lambda x:
                '[{0}: {1}%]'.format(x.mountpoint, psutil.disk_usage(x.mountpoint).percent),
            psutil.disk_partitions()
        )
    )

def run_command(cmd):
    try:
        return (0, subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT))
    except subprocess.SubprocessError as e:
        return (e.returncode, e.output)

class AgentProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        logging.info('Connected to SHIELD server at [{0}]'.format(transport.get_extra_info('peername')))
        self.transport = transport
        self.writejson({'type': 'auth', 'name': config.name, 'fingerprint': config.fingerprint})

    def data_received(self, data):
        try:
            json = simplejson.loads(data)
        except:
            self.transport.close()
            return
        logging.debug('[LINK] >>> {0}'.format(json))
        if json['type'] == 'auth':
            if json['msg'] != 'authenticated':
                self.transport.close()
                return
        elif json['type'] == 'heartbeat':
            if json['msg'] == 'ping':
                self.writejson({'type': 'heartbeat', 'msg': 'pong', 'timestamp': time()})
        elif json['type'] == 'exec':
            @asyncio.coroutine
            def run_command_task(cmd):
                result = run_command(cmd)
                output = result[1].strip().split(b'\n')
                self.writejson({'type': 'exec', 'returncode': result[0], 'output': output})
            asyncio.async(run_command_task(json['command']))

    def _connection_lost(self, exc):
        logging.info('Connection closed')
        self.transport = None

    def writejson(self, d):
        json = simplejson.dumps(d)
        self.transport.write(json.encode('utf-8') + b'\n')
        logging.debug('[LINK] <<< {0}'.format(json))
