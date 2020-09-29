
from time import sleep
import json

import random

import zmq

from zflux.config import Config, argparser

args = argparser().parse_args()
config = Config.read(args.config)

def testcounting_pub():


    context = zmq.Context()
    socket = context.socket(zmq.PUB)

    socket.connect(config.zmq.pub)
    print(config.zmq.pub)

    sleep(5.0)

    i = 0
    try:
        while True:
            j = json.dumps({'fields': {'value': i }}).encode()
            socket.send_multipart([config.zmq.topic, j])
            i += 1

            if i < 10:
                print(f"{i}")
            if i == 10:
                print("...")
    except KeyboardInterrupt:
        print(f"stopped at {i}")

def testcounting_sub():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, config.zmq.topic)

    if config.zmq.bind:
        socket.bind(config.zmq.bind)
    else:
        socket.connect(config.zmq.connect)

    print(config.zmq.connect)

    count = None
    print(count)
    try:
        while True:

            # if random.randint(0, 100) == 1:
            #     print(f'sleeping at {count}')
            #     sleep(5.0)


            _, msg = socket.recv_multipart()
            i = json.loads(msg.decode())['fields']['value']

            if count is None:
                print(f"starting at {i}")
                count = i
            else:
                diff = i - count


                if diff != 1:
                    print(diff)
                    raise SystemExit(diff)


                count = i
    except KeyboardInterrupt:
        print(f"stopped at: {count}")
