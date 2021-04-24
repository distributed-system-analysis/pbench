#!/bin/bash
python3 node1_server.py
port=50051
Local_ip=$(hostname -I)
counter=1
while [ $counter -le 10]
do
	echo From: $1
	ssh $1 python3 < test_client.py $Local_ip $port
	sleep 0.5
	echo From: $2
	ssh $2 python3 < test_client.py $Local_ip $port
	sleep 3.5
	(($counter++))
done