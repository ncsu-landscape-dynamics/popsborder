#!/bin/bash

# This script is used to generate a simplified fully synthetic F280 dataset.

if [ -z "$1" ] || [ -z "$2" ]
  then
    >&2 echo "Usage:"
    >&2 echo "  $0 <output file> <size>"
    exit 1
fi

python -m popsborder --num-simulations 1 --num-consignments "$2" --config-file config.yml --output-file "$1"
