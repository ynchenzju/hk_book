
ps aux | grep slow_trans.py | grep -v grep | awk '{print $2}' | xargs kill
