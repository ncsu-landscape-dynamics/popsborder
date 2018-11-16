#!/bin/sh

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]
  then
    >&2 echo "Usage:\n  $0 <output file> <separator> <size>"
    exit 1
fi

python simulation.py 1 $3 config.yml \
    | grep "F280: " | sed -e 's/F280: //g' \
    | sed -e "s/ /$2/g" > $1
