#!/usr/bin/env python3
"""Сторож homeserver: раз в минуту (homeserver-watchdog.timer, root).

1. Состояние важных контейнеров и наличие GPU по UUID → watchdog.prom для node-exporter;
   алерты считает Prometheus homeserver и шлёт в Alertmanager на VPS vaibkod.
2. Подстраховка ComfyUI: ControlNet/VAE/CLIP кристаллов живут на x1-карте 47984de7 (райзер,
   ловила Xid 79). Пропала из nvidia-smi на 2 проверки подряд → пересоздаём saiga-comfyui
   на одной x4-карте (docker-compose.single-gpu.yml; ноды saiga_device без cuda:1 — no-op).
   Карта снова видна 5 проверок подряд (обычно после ребута) → возвращаем обе карты.
"""
import json
import os
import re
import subprocess
import time

OUT = "/var/lib/node_exporter/textfile_collector/watchdog.prom"
STATE = "/var/lib/homeserver-watchdog/state.json"
COMFY_DIR = "/home/denciao/projects/saiga/comfyui"
COMFY = "saiga-comfyui"
AUX_GPU = "GPU-47984de7-4168-0c8c-efa8-0f93372f4246"
GPUS = {
    "GPU-338bbf4e-a3cf-6a5d-750f-7a7068138c08": "llm x4 (CPU-слот)",
    "GPU-973a0619-a4c1-08d6-04bd-c68217cdf052": "llm x1-райзер",
    "GPU-fa0a96a7-0bf7-96fa-2826-4553b6b62e73": "comfyui x4",
    AUX_GPU: "comfyui aux x1-райзер",
}
CONTAINERS = (
    "caddy", "saiga-llm", "saiga-comfyui", "saiga-embedding", "saiga-postgres",
    "saiga-web-app", "saiga-web-redis", "vaultwarden",
    "artk_backend", "artk_frontend", "artk_postgres", "artk_redis",
    "grafana", "node-exporter", "cadvisor", "dcgm-exporter",
)
DOWN_TO_FALLBACK = 2
UP_TO_RESTORE = 5


def run(cmd, timeout=60, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


def container_ok():
    ok = {}
    p = run(["docker", "inspect", "--format", "{{.Name}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}", *CONTAINERS])
    for line in p.stdout.splitlines():
        name, status, *health = line.lstrip("/").split()
        ok[name] = int(status == "running" and health != ["unhealthy"])
    return {c: ok.get(c, 0) for c in CONTAINERS}


def visible_gpus():
    """UUID из nvidia-smi -L. None — nvidia-smi завис или не запустился: решений не принимаем."""
    try:
        p = run(["nvidia-smi", "-L"], timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        return None
    # При отвалившейся карте nvidia-smi выходит с ошибкой, но живые карты всё равно печатает.
    found = set(re.findall(r"UUID: (GPU-[0-9a-f-]+)", p.stdout))
    return found or None


def comfy_mode():
    p = run(["docker", "inspect", "--format", "{{range .Config.Env}}{{println .}}{{end}}", COMFY])
    if p.returncode:
        return None
    return "dual" if AUX_GPU in p.stdout else "single"


def compose_up(single):
    files = ["-f", "docker-compose.yml"] + (["-f", "docker-compose.single-gpu.yml"] if single else [])
    p = run(["docker", "compose", *files, "up", "-d", COMFY], timeout=300, cwd=COMFY_DIR)
    print(f"compose up {'single' if single else 'dual'}: rc={p.returncode} {p.stderr.strip()[-300:]}", flush=True)
    return p.returncode == 0


def main():
    try:
        with open(STATE) as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    st.setdefault("aux_down", 0)
    st.setdefault("aux_up", 0)
    st.setdefault("last_switch", 0)

    gpus = visible_gpus()
    mode = comfy_mode()
    if gpus is not None:
        if AUX_GPU in gpus:
            st["aux_down"], st["aux_up"] = 0, st["aux_up"] + 1
        else:
            st["aux_down"], st["aux_up"] = st["aux_down"] + 1, 0

        main_gpu_ok = "GPU-fa0a96a7-0bf7-96fa-2826-4553b6b62e73" in gpus
        if mode == "dual" and st["aux_down"] >= DOWN_TO_FALLBACK and main_gpu_ok:
            print(f"{AUX_GPU} пропала {st['aux_down']} проверок подряд — ComfyUI на одну карту", flush=True)
            if compose_up(single=True):
                st["last_switch"], mode = time.time(), "single"
        elif mode == "single" and st["aux_up"] >= UP_TO_RESTORE:
            print(f"{AUX_GPU} снова видна {st['aux_up']} проверок — ComfyUI обратно на две карты", flush=True)
            if compose_up(single=False):
                st["last_switch"], mode = time.time(), "dual"

    lines = [f'homeserver_container_ok{{name="{c}"}} {v}' for c, v in container_ok().items()]
    lines.append(f"homeserver_nvidia_smi_ok {int(gpus is not None)}")
    if gpus is not None:
        lines += [f'homeserver_gpu_present{{uuid="{u}",role="{r}"}} {int(u in gpus)}' for u, r in GPUS.items()]
    if mode is not None:
        lines.append(f"homeserver_comfyui_single_gpu {int(mode == 'single')}")
    lines.append(f"homeserver_comfyui_last_switch_timestamp {st['last_switch']}")

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as fh:
        json.dump(st, fh)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, OUT)


if __name__ == "__main__":
    main()
