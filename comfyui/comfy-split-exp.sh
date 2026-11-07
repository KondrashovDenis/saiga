#!/bin/bash
# Split experiment 2026-11-07: ControlNet/VAE/CLIP on the x1 card (cuda:1), UNet on x4 (cuda:0); lowvram vs normalvram.
set -u
cd /home/denciao/projects/saiga/comfyui
LOG=/home/denciao/nvme-check/comfy-split.log
exec >>"$LOG" 2>&1
echo "=== start $(date) ==="

recreate() {  # flags...
    if [ $# -gt 0 ]; then
        python3 - "$@" <<'EOF'
import sys
p = "docker-compose.yml"
s = open(p).read()
s = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("command:")) + "\n"
cmd = '    command: ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--disable-auto-launch"' + "".join(f', "{f}"' for f in sys.argv[1:]) + ']'
s = s.replace("    restart: unless-stopped\n", "    restart: unless-stopped\n" + cmd + "\n", 1)
open(p, "w").write(s)
EOF
    fi
    docker compose up -d --force-recreate >/dev/null 2>&1
    timeout 300 sh -c "until docker inspect -f {{.State.Health.Status}} saiga-comfyui | grep -q healthy; do sleep 5; done"
    docker cp comfy-test.py saiga-comfyui:/app/comfy-test.py >/dev/null
    echo "[$(date +%T)] recreated: $(grep -m1 'command:' docker-compose.yml || echo 'Dockerfile CMD (--lowvram)')"
}

T() {  # label args...
    local L=$1; shift
    local t0=$(date +%s)
    local r=$(timeout 900 docker exec saiga-comfyui python /app/comfy-test.py --image /app/input/control_image.png --steps 6 --cfg 2.5 \
        --strength 0.85 --size 1024 --seed 777 --out /app/output/split-$L.png "$@" 2>&1 | grep -E "DONE|ERROR|TIMEOUT|Traceback" | tail -1)
    echo "[$(date +%T)] $L: $(( $(date +%s) - t0 ))s | ${r:0:300} | $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader -i 2,3 | tr '\n' ' ')"
}

ALL="--cn-dev cuda:1 --vae-dev cuda:1 --clip-dev cuda:1"
recreate
T low-all-cold $ALL; T low-all-warm $ALL
recreate --normalvram
T normal-all-cold $ALL; T normal-all-warm1 $ALL; T normal-all-warm2 $ALL
docker logs --since 20m saiga-comfyui 2>&1 | grep -E "saiga_device|Prompt executed|loaded (completely|partially)|CLIP/text|VAE load|s/it\]$|Error" | tail -40
echo "=== end $(date) ==="
