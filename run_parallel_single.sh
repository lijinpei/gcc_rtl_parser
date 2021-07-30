#!/bin/sh
if python parse_gcc_rtl.py $1 > /dev/null ;
then
    echo -e "success\t$1"
else
    echo -e "fail\t$1"
fi

