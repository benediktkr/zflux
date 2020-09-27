#!/usr/bin/env python3

import json
from time import sleep
from datetime import datetime
import random

import zmq
from loguru import logger

class StressTester(object):

    def __init__(self, mode, topic=b"test", batch=1, sleepfract=1, verbose=False):
        self.mode = mode
        self.topic = topic
        self.batch = batch
        self.sleepfract = sleepfract
        self.verbose = verbose

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)

        self.i = 0

    def connect(self, addr):
        self.addr = addr
        self.socket.connect(addr)

    def __del__(self):
        self.socket.close()
        self.context.destroy()
        logger.debug("closed socket and destroyed context")

    def mkmsg(self, value):
        return {"tags": {"test": "yes"},
                "fields": {"value": value },
                "measurement": "rand",
                "time": datetime.now().isoformat()}

    def send(self, i):

        if self.mode == "count":
            value = i
        else:
            value = random.randint(0, 100)

        msg = self.mkmsg(value)

        bytemsg = [self.topic, json.dumps(msg).encode()]
        self.socket.send_multipart(bytemsg)

        if self.verbose:
            logger.debug(bytemsg)

        if self.sleepfract and random.randint(0, 10) == 0:
            sleep(0.002)


    def run(self, max_=None):
        i = 0
        while i < max_ or max_ is None:
            i+=1
            self.send(i)
        return i


def main():
    import zflux.config
    conf = zflux.config.Config.read()
    args = zflux.config.args()

    stress = StressTester("count", verbose=args.verbose, sleepfract=100)
    stress.connect(conf.zmq.pub)
    stress.run()
