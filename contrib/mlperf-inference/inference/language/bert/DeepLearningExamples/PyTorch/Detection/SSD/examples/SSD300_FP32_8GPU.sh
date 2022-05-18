# This script launches SSD300 training in FP32 on 8 GPUs using 256 batch size (32 per GPU)
# Usage ./SSD300_FP32_8GPU.sh <path to this repository> <path to dataset> <additional flags>

python -m torch.distributed.launch --nproc_per_node=8 $1/main.py --backbone resnet50 --warmup 300 --bs 32 --data $2 ${@:3}
