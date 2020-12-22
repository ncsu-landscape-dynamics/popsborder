#!/bin/bash

# This file contains examples of using the simulation in Bash.
# To certain extent it will be applicable to other command lines (shells).
# This script can run as is with root of the repo as the current directory.

python -m pathways \
    --num-simulations 100 --num-consignments 1000 --config-file tests/test_summaries/config.yml \
    | grep -E '^slippage: [0-9\.]*$' | sed -e 's/.*=//g'

python -m pathways \
    --num-simulations 1 --num-consignments 20 --config-file tests/test_summaries/config.yml --output-file "-" \
    | grep "F280: " | sed -e 's/F280: //g'
