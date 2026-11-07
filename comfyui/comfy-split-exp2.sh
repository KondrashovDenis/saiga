#!/bin/bash
# Split experiment part 2 (2026-11-08): warm runs with distinct seeds; VAE placement + tiled decode. normalvram container.
set -u
cd /home/denciao/projects/saiga/comfyui
LOG=/home/denciao/nvme-check/comfy-split4.log
exec >>"$LOG" 2>&1
echo "=== start $(date) ==="
docker compose up -d --force-recreate >/dev/null 2>&1; timeout 300 sh -c "until docker inspect -f {{.State.Health.Status}} saiga-comfyui | grep -q healthy; do sleep 5; done"
docker cp comfy-test.py saiga-comfyui:/app/comfy-test.py >/dev/null
SEED=1000

T() {  # label args... ; every run gets a fresh seed so ComfyUI cannot serve a cached result
    local L=$1; shift
    SEED=$((SEED + 1))
    local t0=$(date +%s)
    local r=$(timeout 900 docker exec saiga-comfyui python /app/comfy-test.py --image /app/input/control_image.png --steps 6 --cfg 2.5 \
        --strength 0.85 --size 1024 --seed $SEED --out /app/output/split2-$L.png "$@" 2>&1 | grep -E "DONE|ERROR|TIMEOUT|Traceback" | tail -1)
    local sm=$(docker logs --since "$(( $(date +%s) - t0 + 2 ))s" saiga-comfyui 2>&1 | grep -oE "6/6 \[[0-9:]+<" | tail -1)
    echo "[$(date +%T)] $L seed=$SEED: $(( $(date +%s) - t0 ))s sampling=${sm} | ${r:0:200} | $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader -i 2,3 | tr '\n' ' ')"
}

CC="--cn-dev cuda:1 --clip-dev cuda:1 --cn-fp16 --vae-dev cuda:1"
T cold $CC --vae-mem 3
T mem3-a $CC --vae-mem 3
T mem3-b $CC --vae-mem 3
T mem2-a $CC --vae-mem 2
T mem2-b $CC --vae-mem 2
docker logs --since 15m saiga-comfyui 2>&1 | grep -E "saiga_device|Prompt executed|loaded (completely|partially)|unloaded|Error" | tail -40
echo "=== end $(date) ==="
