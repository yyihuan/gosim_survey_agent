"""仅验证外层超时与进程清理，不参与科学成绩比较。"""
import json
import sys
import time

for line in sys.stdin:
    message = json.loads(line)
    if message.get("message_type") == "decision_request":
        time.sleep(10)
