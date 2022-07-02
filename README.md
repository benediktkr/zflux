# zflux

[![build status](https://jenkins.sudo.is/buildStatus/icon?job=ben%2Fzflux%2Fmain&style=flat-square)](https://jenkins.sudo.is/job/ben/job/zflux/job/main/)

A buffering proxy for InfluxDB, using a zmq SUB socket.

## Overview

This was written as a way to improve reliability of InfluxDB,
especially when the InfluxDB server lives on a different network than
the clients/producers. If the connection between them and the server
goes down, or the server is otherwise unreachable, the client has to
handle the error and buffer datapoints.

The purpose of `zflux` is to sit on the same network as the hosts producing
the data sent to InfluxDB and act as the InfluxDB client. It recieves the
messages from the producers via its SUB socket. If the IfluxDB client cant be
reached, the messages are left in the buffer -- which will be emptied when
the server is reachable.

It supports both using `connect()` and `bind()`, but if both are defined it will default to using `connect()`.

## Configuring

The program looks for a config file in the following order

1. A full file path defined in the `$ZFLUX_CONF` environment variable
2. in `$(pwd)/zflux.yml`
3. in `$HOME/.zflux.yml`
4. in `/usr/local/etc/zflux.yml`
5. in `/etc/zlufx.yml`


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
