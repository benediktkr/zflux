import random
import threading
from time import sleep
import json
from socket import gaierror

from requests.exceptions import RequestException
from influxdb.exceptions import InfluxDBServerError
import pytest
import zmq

from zflux.zflux import Zflux
from zflux.metricscli import get_ruok, get_metrics

EXCEPTIONS = [
    InfluxDBServerError,
    gaierror,
    RequestException,
    ValueError
]

@pytest.fixture()
def resource():
    with ZfluxWithMockedInfluxDB(b"topic", poll_secs=0.1) as z:
        z.socket.set_hwm(0)
        z.listen_metrics("tcp://127.0.13.137:1337")
        z.bind("tcp://127.0.4.20:1337")
        thread = threading.Thread(target=z.run)
        thread.daemon = True
        thread.start()
        yield z
        # make it stop
        z.make_me_stop = True
        # then join the thread for 2 seconds
        thread.join(2)
        assert not thread.is_alive()


class ZfluxWithMockedInfluxDB(Zflux):
    def __init__(self, topic, *args, **kwargs):
        super().__init__(topic, *args, **kwargs)
        self.mock_store = list()
        self.make_me_stop = False

    def check_mock_store(self):
        return len(self.mock_store)

    def handle_recv(self):
        if self.make_me_stop == True:
            raise KeyboardInterrupt
        else:
            super().handle_recv()

    def influxdb_write(self, msgs):
        #assert len(msgs) > 0
        #temp_last = self.last_i

        if random.randint(0, 500) == 2:
            exc = random.choice(EXCEPTIONS)
            raise exc("simulating influxdb server errors")

        for msg in msgs:
            val = msg['fields']['value']
            self.mock_store.append(val)



def test_zflux_object(resource):
    assert resource.topic == b"topic"

def test_ruok(resource):
    status = get_ruok(resource.metrics_addr)
    assert status == b'imok'

def test_metrics(resource):
    metrics = get_metrics(resource.metrics_addr)
    assert 'buffer_size' in metrics
    assert metrics['buffer_size'] == 0
    assert 'influx_at' in metrics


def test_random_msgs(resource):
    count = random.randint(300, 500)

    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.connect(resource.bind_addr)
    socket.setsockopt(zmq.LINGER, 0)

    # slow joiner syndrome
    sleep(0.2)

    def mkpart(value):
        d = {'fields': {'value': value}}
        return json.dumps(d).encode()


    for i in range(count):
        msg = [b"topic", mkpart(i)]
        if random.randint(0, 10) == 0:
            sleep(0.002)
        socket.send_multipart(msg)

    socket.close()
    context.term()

    for _ in range(600):
        if count > len(resource.mock_store):
            sleep(0.1)
        else:
            break

    # its helpful to know if the beginning or end are missing
    assert resource.mock_store[0] == 0
    assert resource.mock_store[-1] == count-1
    assert len(resource.mock_store) == count


    # and check that all of the messages are there
    for i in range(count):
        assert resource.mock_store[i] == i
