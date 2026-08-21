#!/bin/bash
# 看門狗:引擎死掉就重啟,synth 反覆跑到全部完成(已完成自動跳過)
cd /home/claude/full
for round in $(seq 1 40); do
  if ! curl -s --max-time 5 http://127.0.0.1:50021/version >/dev/null; then
    echo "[sup] round $round: restarting engine"
    pkill -f 'run --host 127.0.0.1 --port 50021' 2>/dev/null
    sleep 2
    (cd /tmp/vv/linux-cpu-x64 && nohup ./run --host 127.0.0.1 --port 50021 >> /tmp/vv.log 2>&1 &)
    sleep 30
  fi
  python3 synth_full.py >> synth_full.log 2>&1
  rc=$?
  n=$(ls audio/*.mp3 2>/dev/null | wc -l)
  echo "[sup] round $round done rc=$rc files=$n"
  if [ $rc -eq 0 ]; then echo "[sup] ALL DONE"; break; fi
  sleep 5
done
