#!/bin/bash
# Speed experiments for the crystal workflow on P104-100. Each config: recreate container, wait healthy,
# run the same prompt/seed twice (cold + warm), log times, VRAM, max temp. Restores the baseline compose at the end
# unless KEEP=<name> is given. Launch: systemd-run --unit=comfy-exp --collect /bin/bash comfy-experiments.sh
set -u
D=/home/denciao/projects/saiga/comfyui
LOG=/home/denciao/nvme-check/comfy-experiments.log
exec >>"$LOG" 2>&1
log() { echo "[$(date +%T)] $*"; }
cd "$D"
cp -n docker-compose.yml docker-compose.yml.baseline

GPU_X1=GPU-973a0619-a4c1-08d6-04bd-c68217cdf052   # PCIEX16(G4)_2 USB riser x1
GPU_X4=GPU-fa0a96a7-0bf7-96fa-2826-4553b6b62e73   # PCIEX16(G4)_1 chipset x4 (currently LLM's second card)
LLM=/home/denciao/projects/saiga/llm

set_config() {  # name gpu "flags"
    local NAME=$1 GPU=$2 FLAGS=$3
    cp docker-compose.yml.baseline docker-compose.yml
    sed -i "s#NVIDIA_VISIBLE_DEVICES=GPU-[0-9a-f-]*#NVIDIA_VISIBLE_DEVICES=$GPU#" docker-compose.yml
    # replace CMD via compose command override (insert after container_name line)
    sed -i "/container_name: saiga-comfyui/a\\    command: [\"python\", \"main.py\", \"--listen\", \"0.0.0.0\", \"--port\", \"8188\", \"--disable-auto-launch\"$FLAGS]" docker-compose.yml
    docker compose up -d --force-recreate >/dev/null 2>&1
    for i in $(seq 1 40); do sleep 5; [ "$(docker inspect -f '{{.State.Health.Status}}' saiga-comfyui 2>/dev/null)" = "healthy" ] && break; done
    docker cp comfy-test.py saiga-comfyui:/app/comfy-test.py >/dev/null
    log "config $NAME: gpu=${GPU:4:8} flags=[$FLAGS] health=$(docker inspect -f '{{.State.Health.Status}}' saiga-comfyui)"
}

run_test() {  # label
    local LABEL=$1 IDX
    IDX=$(nvidia-smi --query-gpu=index,gpu_uuid --format=csv,noheader | grep "$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' saiga-comfyui | grep NVIDIA_VISIBLE_DEVICES | cut -d= -f2)" | cut -d, -f1)
    nvidia-smi --query-gpu=temperature.gpu,power.draw,memory.used,utilization.gpu --format=csv,noheader -l 5 -i "$IDX" > /tmp/mon.csv 2>&1 &
    local MON=$!
    local t0=$(date +%s)
    local out
    out=$(timeout 1200 docker exec saiga-comfyui python /app/comfy-test.py --image /app/input/control_image.png --steps 6 --cfg 2.5 --strength 0.85 --size 1024 --seed 777 --out "/app/output/${LABEL}.png" 2>&1 | grep -E "DONE|ERROR|TIMEOUT|Traceback" | tail -1)
    kill $MON 2>/dev/null; wait $MON 2>/dev/null
    local el=$(( $(date +%s) - t0 ))
    log "  $LABEL: ${el}s | $out | $(awk -F', ' '{t=$1+0; if(t>mt)mt=t; p=$2+0; if(p>mp)mp=p; m=$3+0; if(m>mm)mm=m} END {printf "max temp %d C, max power %.0f W, max VRAM %d MiB", mt, mp, mm}' /tmp/mon.csv)"
}

echo "=== experiments start $(date) ==="

# E1: baseline card (x1) + --force-fp16
set_config "x1-forcefp16" "$GPU_X1" ', "--lowvram", "--force-fp16"'
run_test "e1-x1-fp16-cold"; run_test "e1-x1-fp16-warm"

# E2: x4 card (swap with LLM's second card), default precision
log "swap: LLM -> $GPU_X1 as second card, ComfyUI -> x4"
cp -n "$LLM/docker-compose.yml" "$LLM/docker-compose.yml.bak-exp"
sed -i "s#$GPU_X4#$GPU_X1#" "$LLM/docker-compose.yml"
(cd "$LLM" && docker compose up -d --force-recreate >/dev/null 2>&1)
sleep 20
set_config "x4-lowvram" "$GPU_X4" ', "--lowvram"'
run_test "e2-x4-cold"; run_test "e2-x4-warm"

# E3: x4 card + --force-fp16
set_config "x4-forcefp16" "$GPU_X4" ', "--lowvram", "--force-fp16"'
run_test "e3-x4-fp16-cold"; run_test "e3-x4-fp16-warm"

# E4: x4 card + fp8 unet storage (quality A/B only)
set_config "x4-fp8unet" "$GPU_X4" ', "--lowvram", "--fp8_e4m3fn-unet"'
run_test "e4-x4-fp8-cold"; run_test "e4-x4-fp8-warm"

log "LLM state: $(docker ps --format '{{.Names}} {{.Status}}' | grep saiga-llm)"
nvidia-smi --query-compute-apps=process_name,used_memory,gpu_uuid --format=csv,noheader | sed 's#/app/venv.*llama-server#llama-server#'
echo "=== experiments end $(date) (ComfyUI left in last config: x4 + fp8; LLM on x4+x1) ==="
