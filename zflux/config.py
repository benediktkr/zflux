#!/usr/local/bin/env

import os
import sys
from dataclasses import dataclass
import argparse

import yaml

from loguru import logger

def logger_from_env():
    if 'ZFLUX_LOGFILE' in os.environ:
        logfile = os.environ["ZFLUX_LOGFILE"]
        loglevel = os.environ.get("ZFLUX_LOGLEVEL", "DEBUG")
        logger.remove()
        logger.add(sys.stderr, level=loglevel)
        logger.add(logfile, level=loglevel)
        logger.debug("configured logger for env vars")


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

    @classmethod
    def read(cls, path=None):
        logger_from_env()

        if not path:
            locations = [
                os.environ.get("ZFLUX_CONF", ""),
                os.path.join(os.curdir, "zflux.yml"),
                os.path.join(os.path.expanduser("~"), ".zflux.yml"),
                "/usr/local/etc/zflux.yml",
                "/etc/zflux.yml",
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

                    logger.debug(f"using confg file {conffile}")
                try:

                    return cls(
                        name=conffile,
                        zmq=cls.ZmqConfig(**zconf),
                        influxdb=cls.InfluxDBConfig(**inflconf),
                    )
                except TypeError as e:
                    logger.exception(e)
                    raise


            except IOError as e:
                if e.errno == 2: continue
                else: raise
        else:
            logger.error("config file not found")
            raise SystemExit("Config file not found")


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
