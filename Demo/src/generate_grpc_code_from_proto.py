# Calls the gRPC tools command needed to generate server code
# Deletes the previous verions if exist

import os

print("> Removing old pb2 files")
os.system('rm node1_pb2.py node1_pb2_grpc.py')
print("> Generating new code")
os.system('python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. node1.proto')
print("> DONE")