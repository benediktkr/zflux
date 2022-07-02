#!/usr/bin/env python3

import sys
import argparse
from contextlib import contextmanager
import json

import zmq
from loguru import logger
logger.remove()

from zflux.config import Config

@contextmanager
def zmq_metrics(metrics_addr, metric_name):

    timeout = 1000
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(metrics_addr)

    socket.send(metric_name)
    try:
        if (socket.poll(timeout) & zmq.POLLIN) != 0:
            reply = socket.recv()
            yield reply
        else:
            raise TimeoutError(f"timed out waiting {timeout}ms for {metrics_addr}")
    finally:
        # do not linger, otherwise context.term() will block
        socket.setsockopt(zmq.LINGER, 0)
        socket.close()
        context.term()


def get_ruok(metrics_addr):
    # ask if zflux is okay
    with zmq_metrics(metrics_addr, b'ruok') as reply:
        return reply

def get_metrics(metrics_addr):
    # ask if zflux is okay
    with zmq_metrics(metrics_addr, b'metrics') as reply:
        j = json.loads(reply)

    return j


def get_metrics_addr():
    c = Config.read()
    return c.zmq.metrics

def cli_ruok():
    metrics_addr = get_metrics_addr()
    status = get_ruok(metrics_addr)

    if status.lower() == b"imok":
        #logger.success(f"healtcheck passed: {status}")
        sys.exit(0)
    else:
        #logger.error(f"healtcheck failed: {status}")
        sys.exit(1)


def cli_metrics():
    metrics_addr = get_metrics_addr()
    metrics = get_metrics(metrics_addr)
    print(json.dumps(metrics, indent=2))
