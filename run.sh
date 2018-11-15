#!/bin/sh

python simulation.py 100 1000 config.yml | grep result | sed -e 's/.*=//g'
