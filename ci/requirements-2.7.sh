#!/bin/bash

source activate pandas

echo "install 27"

conda install -n pandas -c conda-forge feather-format jemalloc=4.4.0
