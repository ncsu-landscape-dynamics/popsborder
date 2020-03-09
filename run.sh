#!/bin/sh

python -m pathways --num-simulations 100 --num-shipments 1000 --config-file config.yml \
    | grep -E '^slippage: [0-9\.]*$' | sed -e 's/.*=//g'

python -m pathways --num-simulations 1 --num-shipments 20 --config-file config.yml --output-file "-" \
    | grep "F280: " | sed -e 's/F280: //g'
