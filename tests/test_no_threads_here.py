import pytest

from zflux.zflux import Zflux
from zflux.config import Config
from zflux.metricscli import get_ruok

@pytest.fixture()
def resource():
    c = Config.read('test-zflux-local.yml')
    z = Zflux(c.zmq.topic)
    z.bind(c.zmq.bind, c.zmq.metrics)
    yield z

    # tear down
    z.close()


class TestZflux:

    def test_read_config(self):
        c = Config.read('test-zflux-local.yml')
        assert c.zmq is not None
        assert c.zmq.topic is not None

    def test_zflux_object(self, resource):
        c = Config.read('test-zflux-local.yml')
        assert resource.topic == c.zmq.topic

    # def test_test(self, resource):
    #     c = Config.read('test-zflux-local.yml')
    #     isok = get_ruok(c.zmq.metrics)
    #     assert isok == b"imok"
    #     assert resource.topic == c.zmq.topic
