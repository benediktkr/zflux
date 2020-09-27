import threading
from time import sleep, time

import random

import zmq.error
from requests.exceptions import RequestException
from loguru import logger

from zflux.zflux import Zflux
from zflux.config import Config
from zflux.stresstester import StressTester

logger.add("unittest.log")
logger.info("-----")

class StopTestingMe(Exception): pass


class Zflux2(Zflux):
    def __init__(self, topic, count, *args, **kwargs):

        self.fake_influxdb_errors = kwargs.pop('fake_influxdb_errors', True)
        if not self.fake_influxdb_errors:
            logger.warning("no influxdb errors simulated")
        self.last_i = None
        self.missed = 0
        self.count = count
        super().__init__(topic, *args, **kwargs)

    def influxdb_write(self, msgs):

        assert len(msgs) > 0

        temp_last = self.last_i
        for msg in msgs:
            val = msg['fields']['value']
            if temp_last is not None:
                diff = val - temp_last
                assert diff == 1, diff
                temp_last = val

            else:
                logger.warning(f"start: {val}")
                temp_last = val

        self.last_i = temp_last
        if self.last_i >= self.count:
            raise StopTestingMe


    def influxdb_write2(self, msgs):
        if len(msgs) > self.batch or len(msgs) == 0:
            raise ValueError("just send one chunk")

        last_val = self.last_i
        if last_val is None:
            next_ = msgs[0]['fields']['value']
            if next_ != 0:
                self.missed = next_
                logger.warning(f"start: {self.missed}")
            last_val = next_-1

        for msg in msgs:
            val = msg['fields']['value']
            diff = val - last_val

            assert val > last_val, f"new value sould be larger, {val}>{last_val}"
            assert diff == 1, f"{diff} == 1, val: {val}, last_val: {last_val}"

            # if diff == 0 and last_val == 0:
            #     # starting from 0 is a speial case
            #     pass
            if self.fake_influxdb_errors:
                if random.randint(0, 100) < random.randint(0, 10):
                    raise RequestException("simulating errors")

            # if val % 1000 == 0:
            #     logger.info(f"{val}/{self.count}")
            last_val = val

        if last_val >= self.count:
            logger.info(f"got {val}/{self.count} messags in order")
            raise StopTestingMe

        self.last_i = last_val

        return True


class Job(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.shutdown_flag = threading.Event()

    def stop(self):
        assert self.is_alive()
        self.shutdown_flag.set()

        while self.is_alive():
            sleep(0.1)

        logger.info("thread stopped")
        return True

    def wait(self):
        while not self.shutdown_flag.is_set():
            sleep(1.0)


class ZfluxJob(Job):
    def __init__(self, conf, count, *args, **kwargs):
        super().__init__()

        self.conf = conf
        self.count = count
        self.zflux = Zflux2(conf.zmq.topic, count, **kwargs)

        self.zflux.socket.set_hwm(0)


        if conf.zmq.connect:
            logger.debug(f"connectig to {conf.zmq.connect}")
            self.zflux.connect(conf.zmq.connect)
        else:
            logger.debug(f"binding on {conf.zmq.bind}")
            self.zflux.bind(conf.zmq.bind)

        logger.info(f"expecting {count} messages")

    def run(self):
        try:
            self.zflux.run()
        except StopTestingMe:

            return True
        except Exception:
            raise

class StressJob(Job):
    def __init__(self, conf, count, *args, **kwargs):

        self.conf = conf
        self.count = count
        self.stress = StressTester("count", topic=conf.zmq.topic)
        self.stress.socket.setsockopt(zmq.LINGER, -1)
        super().__init__()

        logger.info(f"stressing to {conf.zmq.pub}")
        self.stress.connect(conf.zmq.pub)

        sleep(1.0)

    def run(self):
        #c = self.stress.run()
        #assert c == self.count, f"{c} == {self.count}"

        i = 0
        while not self.shutdown_flag.is_set():
            i+=1
            self.stress.send(i)
        logger.info(f"sent {i} messages")

        return i


def test_counting_proxy():
    conf = Config.read('test-zflux-proxy.yml')
    count = random.randint(3000, 5000)

    run_test_threads(conf, count)

def test_counting_local_defaults():
    conf = Config.read('test-zflux-local.yml')
    count = random.randint(3000, 5000)

    run_test_threads(conf, count)

def test_counting_local_noerrors():
    conf = Config.read('test-zflux-local.yml')
    count = random.randint(3000, 5000)

    run_test_threads(conf, count, fake_influxdb_errors=False)

def test_counting_proxy_noerrors():
    conf = Config.read('test-zflux-proxy.yml')
    count = random.randint(3000, 5000)

    run_test_threads(conf, count, fake_influxdb_errors=False)

def test_counting_proxy_1sec():
    conf = Config.read('test-zflux-proxy.yml')
    count = random.randint(3000, 5000)

    run_test_threads(conf, count, poll_secs=1.0)

def test_counting_proxy2():
    conf = Config.read('test-zflux-proxy.yml')
    count = random.randint(3000, 5000)

    run_test_threads(conf, count, max_age=1.0, batch=100, poll_secs=1.0)


def run_test_threads(conf, count, **kwargs):
    zflux_thread = ZfluxJob(conf, count, **kwargs)
    zflux_thread.start()

    sleep(2)

    stress_thread = StressJob(conf, count)
    stress_thread.start()

    zflux_thread.join(timeout=120)
    assert (not zflux_thread.is_alive()), "sub thread still alive"

    stress_thread.stop()
    assert not stress_thread.is_alive()

    logger.info("finished")
    return True


def main():

    test_counting_proxy()


def test_zflux_version():
    from zflux import __version__
    assert __version__ == '0.1.0'
