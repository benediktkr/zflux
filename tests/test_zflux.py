import threading
from time import sleep

import random

import zmq.error
from requests.exceptions import RequestException
from loguru import logger

from zflux.zflux import Zflux
from zflux.config import Config
from zflux.stresstester import StressTester

conf = Config.read('test-zflux-proxy.yml')
logger.remove()
logger.add("unittest.log")
logger.info("-----")
logger.info(conf)


class StopTestingMe(Exception): pass


class Zflux2(Zflux):
    def influxdb_write(self, msgs):
        if len(msgs) > self.batch:
            raise ValueError("just send one chunk")


        last_val = self.last_i
        if last_val == 0:
            next_ = msgs[0]['fields']['value']
            if next_ == 0:
                self.missed = next_ - len(msgs)
            else:
                last_val = next_ - 1

        for msg in msgs:
            val = msg['fields']['value']
            diff = val - last_val

            if diff != 1:
                raise ValueError(val, last_val)

            if random.randint(0, 100) < random.randint(0, 15):
                raise RequestException("simulating errors")
            last_val = val


        self.total_writes += len(msgs)

        self.last_i = last_val
        if self.target_count < self.last_i:

            extra = self.last_i - self.target_count
            if extra > len(msgs):
                raise ValueError("should not happen")
            self.total = self.last_i - extra
            assert self.total == self.target_count



            raise StopTestingMe(self.last_i)

        return True


def zflux_sub():
    z = Zflux2(conf.zmq.topic)

    z.last_i = 0
    z.target_count=random.randint(2000, 30000)
    z.missed = 0
    z.total_writes = 0

    if conf.zmq.connect:
        z.connect(conf.zmq.connect)
    else:
        z.bind(conf.zmq.bind)

    logger.info("target: " + str(z.target_count))
    logger.remove()
    try:

        z.run()
    except StopTestingMe:
        logger.add("unittest.log")

        logger.info("missed: " + str(z.missed))

        logger.info("done")
        return


def stress_pub():
    s = StressTester("count", topic=conf.zmq.topic, sleepfract=1000)
    s.connect(conf.zmq.pub)
    sleep(3)


    s.run()

def test_proxy_counting():

    try:
        zflux_thread = threading.Thread(target=zflux_sub)
        zflux_thread.daemon = True
        stress_thread = threading.Thread(target=stress_pub)
        stress_thread.daemon = True

        zflux_thread.start()
        stress_thread.start()

        zflux_thread.join()

    except StopTestingMe:
        logger.info("got signal to stop testing")
        stress_thread.stop()
        zflux_thread.stop()


def main():
    test_proxy_counting()

def test_zflux_version():
    from zflux import __version__
    assert __version__ == '0.1.0'
