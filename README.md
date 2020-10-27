# zflux

A buffering proxy for InfluxDB, using a zmq SUB socket.

## Overview

The usecase this was written to improve reliability of InfluxDB,
especially when the InfluxDB server is on a different network than the
clients. If the connection goes down, or the server is unreachable,
the client has to handle the error and buffer datapoints.

The purpose of `zflux` is to sit on the same network as the hosts producing
the data sent to InfluxDB and act as the InfluxDB client. It recieves the
messages from the producers via its SUB socket. If the IfluxDB client is not
reached, the messages get added to the buffer which is then emptied when
the server is responsive again.

It supports both using `connect()` and `bind()`, but if both are defined it will default to using `connect()`.

## Configuring

The program looks for a config file in the following order

1. A full file path defined in the `$ZFLUX_CONF` environment variable
2. in `$HOME/.zflux.yml`
3. in `/usr/local/etc/zflux.yml`
4. in `/etc/zlufx.yml`
5. in `$(pwd)/zflux.yml`

### Sample config

```yml
---

zmq:
  topic: 'zflux'
  connect: 'tcp://$zmq_proxy:5560'
  # alternatively you can use bind()
  #bind: 'tcp://*:5559'

influxdb:
  host: influxdb.example.com
  db: $influxdb_database
  user: $influxdb_username
  passwd: $influxdb_hostname

```
