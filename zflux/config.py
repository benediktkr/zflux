#!/usr/local/bin/env

import os
import sys
from dataclasses import dataclass
import argparse

import yaml

from loguru import logger

@dataclass
class Config:

    @dataclass
    class ZmqConfig:
        topic: bytes
        bind: str = None
        connect: str = None
        pub: str = None

        def __post_init__(self):

            if not self.bind and not self.connect:
                raise TypeError("must set either 'bind' or 'connect'")
            if self.bind and self.connect:
                logger.warning("both 'zmq.bind' and 'zmq.connect' are defined, unsetting 'bind'")
                self.bind = None

            if not isinstance(self.topic, bytes):
                self.topic = self.topic.encode()

    @dataclass
    class InfluxDBConfig:
        host: str
        db: str
        user: str
        passwd: str

    name: str
    zmq: ZmqConfig
    influxdb: InfluxDBConfig
    test: bool = False

    @classmethod
    def read(cls, path=None):

        if not path:
            locations = [
                os.environ.get("ZFLUX_CONF", ""),
                os.path.join(os.path.expanduser("~"), ".zflux.yml"),
                "/usr/local/etc/zflux.yml",
                '/etc/zflux.yml',
                os.path.join(os.curdir, "zflux.yml")
            ]
        else:
            if path.startswith("/"):
                locations = [path]
            else:
                locations = [os.path.join(os.curdir, path)]


        for conffile in locations:

            try:
                with open(conffile, 'r') as cf:
                    yconfig = yaml.safe_load(cf)
                    zconf = yconfig['zmq']
                    inflconf = yconfig['influxdb']
                    testconf = yconfig.get('test', False)
                try:
                    if not testconf:
                        import sys
                        logger.remove()
                        logger.add(sys.stderr, backtrace=False, diagnose=False)

                    return cls(
                        name=conffile,
                        zmq=cls.ZmqConfig(**zconf),
                        influxdb=cls.InfluxDBConfig(**inflconf),
                        test=False
                    )
                except TypeError as e:
                    logger.exception(e)
                    raise


            except IOError as e:
                if e.errno == 2: continue
                else: raise
        else:
            logger.error(f"Config file 'zflux.yml' not found anywhere")
            sys.exit(1)

    def as_dict(self):
        return vars(**self)


def argparser():
    parser = argparse.ArgumentParser(
        "zflux",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-c", "--config", type=str)
    return parser

def args():
    return argparser().parse_args()


if __name__ == "__main__":
    _args = args()
    config = Config.read(_args.config)
    print(config)
