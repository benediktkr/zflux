#!/usr/bin/env python3

from time import time
import json
from dataclasses import dataclass

from collections import deque
from itertools import islice

import zmq
from loguru import logger
from influxdb import InfluxDBClient

# exceptions influxdb throws
from socket import gaierror
from requests.exceptions import RequestException
from influxdb.exceptions import InfluxDBServerError, InfluxDBClientError

def exc_str(exception):
    return f"{type(exception).__name__}: {exception}"

@dataclass
class BufferInfluxDB:
    influxdb: InfluxDBClient
    queue: deque = deque()
    influx_at: int = int(time())
    max_age: int = 2
    batch_size: int = 100

    def __str__(self):
        return f"<{self.influxdb._host}:{self.influxdb._port} [{len(self.queue)}]>"

    @property
    def ready_send(self):
        now = int(time())
        tt_wait = now-self.influx_at

        if len(self.queue) > self.batch_size or tt_wait < self.max_age:
            self.send_buffer()

    def send_buffer(self):
        while len(self.queue) > 0:
            thisbatch = list(islice(self.queue, batch_size))

            self.write(thisbatch)

            for _ in range(len(thisbatch)):
                msg = self.queue.popleft()
                logger.success(msg)

    def write(self, msgs):
        if len(msgs) > self.batch_size:
            raise ValueError("just send one chunk")

        write = self.influxdb.write_points(
            msgs,
            time_precision=self.precision,
            batch_size=self.batch_size)

        if not write:
            raise ValueError("influxdb client write returned False")


        return len(msgs)


class Zflux(object):

    def __init__(self, topic, batch=4, max_age=2, poll_secs=10, precision='m'):
        """
        influxdb_client: InfluxDBClient object
        batch: how many messages to send to influxdb at a time
        max_age: if theres a backlog, send every max_age seconds to influxdb
        poll_secs: duration of polling loop

        messages are sent when it has been max_age seconds since last attempt OR
        there are batch messages in the buffer


        """
        self.topic = topic
        self.poll_secs = poll_secs
        self.batch = batch
        self.max_age = max_age
        self.precision = precision
        self.upstream = dict()
        self.influxdb_timeout = 2.0

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


    def add_influxdb(self, host, db, user, passwd, port=443):
        name = f"{host}:{port}"

        influxdb_client = InfluxDBClient(
            host=host,
            port=port,
            ssl=True,
            verify_ssl=True,
            timeout=self.influxdb_timeout,
            database=db,
            username=user,
            password=passwd)

        self.upstream[name] = BufferInfluxDB(
            influxdb=influxdb_client,
            max_age=self.max_age,
            batch_size=self.batch)

    @property
    def queue_size(self):
        upstream_clients = self.upstream.values()
        if len(upstream_clients) == 0:
            raise ValueError("No InfluxDBClient instances")

        # define the length of the larger queue as the overall queue size
        return max([len(u.queue) for u in upstream_clients])


    def handle_socket(self):
        polled = dict(self.poller.poll(timeout=self.poll_secs*1000))

        if self.socket in polled and polled[self.socket] == zmq.POLLIN:
            topic, msg = self.socket.recv_multipart()

            jmsg = json.loads(msg.decode())
            logger.debug(jmsg)
            self._buffer_add([ (topic, jmsg) ])

    def _buffer_add(messages):
        msgs = [m[1] for m in msgs]

        for name in self.upstream.keys():
            # add the messagse on the dequeue for every upstream influxdb
            self.upstream[n].extend(msgs)

    def log(self):
        buffers = [f"{a}" for a in self.upstream.values()]
        logger.info(buffers)

    def run(self):
        try:
            while True:
                self.log()
                self.handle_socket()
                self.handle_buffers()

        except KeyboardInterrupt:
            logger.info("exiting")
            for name in self.upstream.keys():
                if len(self.upstream[name].queue) > 0:
                    logger.info(f"flushing: {self.upstream[name]}")
                    try:
                        self.upstream[name].send_buffer()
                    except Exception as e:
                        # since we are exiting, just print any error and continue
                        # to next upstream, if any
                        logger.error(e)
                else:
                    logger.info(f"buffer {self.upstream[name]} empty")


            raise SystemExit

    def handle_buffers(self):
        for name in self.upstream.keys():
            try:

                if len(self.upstream[name].queue) <= self.batch:

                    # if the buffer is within our max batch size limit
                    # then immediately attempt to send the buffer

                    self.upstream[name].send_buffer()

                elif self.upstream[name].ready_send:

                    # if we have more than the batch size limit it means that
                    # a previous message has sent, so we start to only send every
                    # self.max_age seconds, but that means we send self.batch number
                    # of messages at once.

                    # this can lead to building up a backlog, but we won't be busy
                    # waiting for the http call writing to influxdb, instead messages
                    # are kept in the buffers.

                    # this respects the influx_at property, and will be False
                    # if the next influx_at is too far into the future, as a strategy
                    # to avoid waiting for errors such as timeouts

                    self.upstream[name].send_buffer()

                self.upstream[name].influx_at = int(time()) + self.max_age

            except InfluxDBClientError as e:
                # client errors are f.ex. invalid format or bad auth. those requeusts
                # will not succeed by trying again so we bail (maybe improve later?)
                logger.error(exc_str(e))
                raise SystemExit(1)

            except (InfluxDBServerError, gaierror, RequestException, ValueError) as e:
                #if isinstance(e, InfluxDBServerError) and e.args[0]['error'] == 'timeout':
                #    # influxdb.exceptions.InfluxDBServerError: {"error":"timeout"}
                wait = self.max_age*3
                logger.warning(exc_str(e))

                logger.warning(f"{self} was asked to wait: {wait}s")
                self.upstream[name].influx_at = time() + wait





def main():

    import zflux.config
    conf = zflux.config.Config.read()

    zflux = Zflux(conf.zmq.topic)
    if conf.zmq.connect:
        zflux.connect(conf.zmq.connect)
    else:
        zflux.bind(conf.zmq.bind)

    for influxdb in conf.influxdb:
        zflux.add_influxdb(**vars(influxdb))

    zflux.run()
