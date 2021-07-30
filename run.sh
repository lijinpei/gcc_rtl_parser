#!/bin/sh

for i in $1/gcc/config/*/*.md ;
do
    if python parse_gcc_rtl.py $i > /dev/null ;
    then
        echo -e "success\t$i"
    else
        echo -e "fail\t$i"
    fi
done
