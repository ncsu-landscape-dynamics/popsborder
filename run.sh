#!/bin/sh

python simulation.py 100 1000 config.yml \
    | grep "result" | sed -e 's/.*=//g'

python simulation.py 1 20 config.yml \
    | grep "F280: " | sed -e 's/F280: //g' \
    | sed -e 's/ / | /g' | sed -e 's/^/| /g' | sed -e 's/$/ |/g'
