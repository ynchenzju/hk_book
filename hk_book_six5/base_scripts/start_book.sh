#!/bin/bash

cnt=0
total_cnt=0

while true; do
  python hk_book.py >> py_log
  if [ $? -ne 0 ];then
      echo "run hk_book.py failed, please check!"
      exit 1
  fi
  cnt=$((cnt + 1))
  total_cnt=$((total_cnt + 1))
  if [ $cnt -eq 120 ]; then
      cnt=0
      time_str=`date +%Y/%m/%d-%H:%M`
      echo "run after half hour: "$time_str
  fi
  echo "total_cnt: "$total_cnt
  sleep 15
done

