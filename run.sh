#!/bin/sh

python simulation.py --num-simulations 100 --num-shipments 1000 --config-file config.yml \
    | grep -E '^slippage: [0-9\.]*$' | sed -e 's/.*=//g'

python simulation.py --num-simulations 1 --num-shipments 20 --config-file config.yml \
    | grep "F280: " | sed -e 's/F280: //g'
