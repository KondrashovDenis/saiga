#!/usr/bin/env python3
"""SMART всех дисков homeserver → textfile collector node-exporter (smart.prom).

Запускается root'ом из homeserver-smart.timer. Пишет атомарно (tmp + rename),
чтобы node-exporter не прочитал полфайла.
"""
import json
import os
import subprocess

OUT = "/var/lib/node_exporter/textfile_collector/smart.prom"
SMARTCTL = "/usr/sbin/smartctl"
ATA_ATTRS = {5: "reallocated_sectors", 197: "pending_sectors", 198: "offline_uncorrectable", 199: "udma_crc_errors"}
NVME_FIELDS = ("critical_warning", "available_spare", "available_spare_threshold", "percentage_used", "media_errors")


def smartctl(*args):
    p = subprocess.run([SMARTCTL, "-j", *args], capture_output=True, text=True, timeout=60)
    return json.loads(p.stdout)


def esc(v):
    return str(v).replace("\\", "\\\\").replace('"', '\\"')


def main():
    lines = []
    devices = smartctl("--scan").get("devices", [])
    for d in devices:
        dev = d["name"]
        try:
            j = smartctl("-H", "-A", "-i", dev)
        except Exception:
            lines.append(f'smart_scrape_ok{{device="{dev}"}} 0')
            continue
        dtype = j.get("device", {}).get("type", "")
        lbl = f'device="{dev}",type="{dtype}",model="{esc(j.get("model_name", ""))}",serial="{esc(j.get("serial_number", ""))}"'
        # Биты 0-2 exit_status — ошибки самого smartctl (нет устройства, команда не прошла).
        lines.append(f"smart_scrape_ok{{{lbl}}} {0 if j['smartctl']['exit_status'] & 0b111 else 1}")
        passed = j.get("smart_status", {}).get("passed")
        if passed is not None:
            lines.append(f"smart_health_passed{{{lbl}}} {int(passed)}")
        temp = j.get("temperature", {}).get("current")
        if temp is not None:
            lines.append(f"smart_temperature_celsius{{{lbl}}} {temp}")
        for a in j.get("ata_smart_attributes", {}).get("table", []):
            name = ATA_ATTRS.get(a["id"])
            if name:
                lines.append(f'smart_ata_attribute_raw{{{lbl},attr="{name}"}} {a["raw"]["value"]}')
        nv = j.get("nvme_smart_health_information_log")
        if nv:
            for f in NVME_FIELDS:
                if f in nv:
                    lines.append(f"smart_nvme_{f}{{{lbl}}} {nv[f]}")
    tmp = OUT + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, OUT)


if __name__ == "__main__":
    main()
