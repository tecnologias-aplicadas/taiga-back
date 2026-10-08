#!/bin/bash
 
rabbitmqctl add_vhost taiga
rabbitmqctl set_permissions -p taiga rabbitmquser ".*" ".*" ".*"