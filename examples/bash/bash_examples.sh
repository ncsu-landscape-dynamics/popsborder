#!/bin/bash

# This file contains examples of using the simulation in Bash.
# To certain extent it will be applicable to other command lines (shells).
# This script can run as is in its directory in the repo.

python -m popsborder \
    --num-simulations 10 --num-consignments 100 --config-file config.yml \
    | grep -E '^slippage: [0-9\.]*$' | sed -e 's/.*=//g'

python -m popsborder \
    --num-simulations 1 --num-consignments 20 --config-file config.yml --output-file - \
    | grep "F280: " | sed -e 's/F280: //g'
