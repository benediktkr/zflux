#!/usr/bin/env python3

import json
from time import sleep
from datetime import datetime
import random

import zmq
from loguru import logger

class StressTester(object):

    def __init__(self, mode, topic=b"test", batch=1, sleep=False, verbose=False):
        self.mode = mode
        self.topic = topic
        self.batch = batch
        self.sleep = sleep
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
        return {'fields': {'value': value}}
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

        if self.sleep and random.randint(0, 10) == 0:
            sleep(0.002)


    def run(self, max_=None):
        i = 0
        while max_ is None or i < max_:
            i+=1
            self.send(i)
        return i


def run_stresser():
    import zflux.config
    conf = zflux.config.Config.read()
    args = zflux.config.args()

    stress = StressTester("count", verbose=args.verbose, sleep=False)
    stress.connect(conf.zmq.pub)
    stress.run()

def stresssub():
    from zflux.config import argparser
    args = argparser().parse_args()
    conf = Config.read(args.config)
    zflux = Zflux2(conf.zmq.topic , count=100000, batch=5)
    #zflux.socket.set_hwm(0)

    if conf.zmq.connect:
        logger.debug(f"connectig to {conf.zmq.connect}")
        zflux.connect(conf.zmq.connect)
    else:
        logger.debug(f"binding on {conf.zmq.bind}")
        zflux.bind(conf.zmq.bind)

    zflux.run()
