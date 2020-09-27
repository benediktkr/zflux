#!/usr/bin/env python3

from time import time
import json

from collections import deque
from itertools import islice

import zmq
from loguru import logger
from influxdb import InfluxDBClient

# exceptions influxdb throws
from socket import gaierror
from requests.exceptions import RequestException

class Zflux(object):

    def __init__(self, topic, batch=4, max_age=5, poll_secs=10):
        """
        influxdb_client: InfluxDBClient object
        batch: how many messages to send to influxdb at a time
        max_age: how long a msg is kept in memory before trying to send it
        poll_secs: duration of polling loop

        messages are sent when it has been max_age seconds since last attempt OR
        there are batch messages in the bufger


        """
        self.topic = topic
        self.poll_secs = poll_secs
        self.batch = batch
        self.max_age=max_age

        self.influx_at = time()
        self.buffer = deque()

        # PUSH/PULL is round-robin
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, self.topic)

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

    def __del__(self):
        self.socket.close()
        self.context.destroy()

    def connect(self, addr):
        self.addr = addr
        self.socket.connect(addr)

    def bind(self, addr):
        self.socket.bind(addr)

    def influxdb_setup(self, host, db, user, passwd, timeout=5, precision='m'):
        self.influxdb_client = InfluxDBClient(
            host=host,
            port=443,
            ssl=True,
            verify_ssl=True,
            timeout=timeout,
            database=db,
            username=user,
            password=passwd)
        self.influxdb_precision = precision

    def influxdb_write(self, msgs):

        if len(msgs) > self.batch:
            raise ValueError("just send one chunk")

        write = self.influxdb_client.write_points(
            msgs,
            time_precision=self.preicision,
            batch_size=self.batch)
        if not write:
            raise ValueError("influxdb client write returned False")
        return len(msgs)


    def run(self):
        try:
            while True:
                self.handle()

        except KeyboardInterrupt:
            logger.info("exiting")
            raise SystemExit

    def handle(self):
        polled = dict(self.poller.poll(timeout=self.poll_secs*1000))

        if self.socket in polled:
            topic, msg = self.socket.recv_multipart()
            # topic is not used but very probably will be
            jmsg = json.loads(msg.decode())

            self.buffer.append(jmsg)

        now = time()
        count = len(self.buffer)
        if count > 0 and (count > self.batch or self.influx_at+self.max_age < now):
            try:
                while len(self.buffer) > 0:
                    thisbatch = list(islice(self.buffer, self.batch))
                    self.influxdb_write(thisbatch)
                    self.influx_at = time()

                    for _ in thisbatch:
                        self.buffer.popleft()


            except (gaierror, RequestException, ValueError) as e:
                if e.args[0].startswith("simulating"):
                    logger.debug(e)
                else:
                    logger.error(e)

def main():
    logger.info("started")

    import zflux.config
    conf = zflux.config.Config.read()

    zflux = Zflux(conf.zmq.topic)
    zflux.connect(conf.zmq.connect)
    zflux.influxdb_setup(**vars(conf.influxdb))

    zflux.run()
