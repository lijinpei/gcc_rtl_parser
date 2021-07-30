#!/bin/sh

ls $1/gcc/config/*/*.md | parallel ./run_parallel_single.sh 

