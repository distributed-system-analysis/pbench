import os
import sys
import time
import socket

dest = sys.argv[1]
port = 50051
local_ip = socket.gethostname()
# local_ip = "$(hostname -I)"

for _ in range(10):
	print(f"From: {dest}")
	os.system(f"ssh {dest} python3 < test_client.py {local_ip} {port}")
    # os.system(f"ssh {dest} test_client.py {local_ip} {port}")
	time.sleep(0.5)
