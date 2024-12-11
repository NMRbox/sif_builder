#!/bin/bash
ORIGIN=$(dirname $(readlink -f $0))
sudo ln -s $ORIGIN/venv/bin/sifbuilder /usr/local/bin
