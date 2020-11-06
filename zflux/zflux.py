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
from influxdb.exceptions import InfluxDBServerError

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
        logger.info(f"connected to {addr}")

    def bind(self, addr):
        logger.info(f"binding to {addr}")
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
                self.handle_recv()
                if len(self.buffer) > 0:
                    self.handle_buffer()

        except KeyboardInterrupt:
            if len(self.buffer) > 0:
                logger.info(f"nonempty buffer {len(self.buffer)}, flushing")
                try:
                    self.send_buffer()
                except Exception as e:
                    logger.error(e)

            logger.info("exiting")
            raise SystemExit


    def handle_recv(self):
        polled = dict(self.poller.poll(timeout=self.poll_secs*1000))

        if self.socket in polled and polled[self.socket] == zmq.POLLIN:
            topic, msg = self.socket.recv_multipart()
            # topic is not used but very probably will be
            jmsg = json.loads(msg.decode())

            self.buffer.append(jmsg)

    def handle_buffer(self):

        now = time()
        count = len(self.buffer)
        if (now > self.influx_at + self.max_age) or (count > self.batch):
            self.send_buffer()

    def send_buffer(self):
            try:
                while len(self.buffer) > 0:
                    thisbatch = list(islice(self.buffer, self.batch))
                    #thisbatch = self.buffer[:1]
                    self.influxdb_write(thisbatch)
                    self.influx_at = time()

                    for _ in range(len(thisbatch)):
                        self.buffer.popleft()
            except (gaierror, RequestException, ValueError) as e:
                if e.args[0].startswith("simulating"):
                    logger.debug(e)
                else:
                    logger.error(e)
                return 0
            except InfluxDBServerError as e:
                if e.args[0]['error'] == 'timeout':
                    # influxdb.exceptions.InfluxDBServerError: {"error":"timeout"}
                    logger.error(e)
                else:
                    raise e

def main():

    import zflux.config
    conf = zflux.config.Config.read()

    zflux = Zflux(conf.zmq.topic)
    if conf.zmq.connect:
        zflux.connect(conf.zmq.connect)
    else:
        zflux.bind(conf.zmq.bind)
    zflux.influxdb_setup(**vars(conf.influxdb))

    zflux.run()
