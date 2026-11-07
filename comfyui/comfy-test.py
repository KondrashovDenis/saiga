#!/usr/bin/env python3
"""Smoke test of the healspirit crystal workflow against a ComfyUI API (run inside the container: localhost:8188).
Uploads a control image, submits the same graph as glow_crystals/imagegen_client.py, polls history, saves the PNG.
Usage: python comfy-test.py --image /app/input/control_image.png --steps 6 --cfg 2.5 --strength 0.85 --out /app/output/test.png
Split across GPUs (custom_nodes/saiga_device.py): --cn-dev cuda:1 --vae-dev cuda:1 --clip-dev cuda:1
"""
import argparse, json, time, uuid, urllib.request, urllib.parse, mimetypes, os, sys

BASE = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
CKPT = "sd_xl_turbo_1.0_fp16.safetensors"
CN = "xinsir-canny-sdxl-1.0.safetensors"

def http(method, path, data=None, headers=None, timeout=60):
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()

def upload(path):
    name = os.path.basename(path)
    boundary = "----saiga" + uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: {mimetypes.guess_type(name)[0] or 'image/png'}\r\n\r\n").encode() + open(path, "rb").read() + \
           f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
    st, out = http("POST", "/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    j = json.loads(out)
    return j["name"], j.get("subfolder", "")

def workflow(prompt, negative, image_ref, seed, steps, cfg, w, h, strength, cn_dev="", vae_dev="", clip_dev="", tiled=0, cn_fp16=False, vae_mem=0.0):
    wf = {
        "1": {"inputs": {"ckpt_name": CKPT}, "class_type": "CheckpointLoaderSimple"},
        "2": {"inputs": {"text": prompt, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "3": {"inputs": {"text": negative, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "4": {"inputs": {"image": image_ref, "upload": "image"}, "class_type": "LoadImage"},
        "5": {"inputs": {"control_net_name": CN}, "class_type": "ControlNetLoader"},
        "6": {"inputs": {"positive": ["2", 0], "negative": ["3", 0], "control_net": ["5", 0], "image": ["4", 0],
                         "strength": strength, "start_percent": 0.0, "end_percent": 1.0},
              "class_type": "ControlNetApplyAdvanced"},
        "7": {"inputs": {"width": w, "height": h, "batch_size": 1}, "class_type": "EmptyLatentImage"},
        "8": {"inputs": {"seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler_ancestral",
                         "scheduler": "sgm_uniform", "denoise": 1.0, "model": ["1", 0],
                         "positive": ["6", 0], "negative": ["6", 1], "latent_image": ["7", 0]},
              "class_type": "KSampler"},
        "9": {"inputs": {"samples": ["8", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
        "10": {"inputs": {"images": ["9", 0], "filename_prefix": "saiga_test"}, "class_type": "SaveImage"},
    }
    if clip_dev:
        wf["13"] = {"inputs": {"clip": ["1", 1], "device": clip_dev}, "class_type": "SaigaCLIPDevice"}
        wf["2"]["inputs"]["clip"] = wf["3"]["inputs"]["clip"] = ["13", 0]
    if cn_dev and cn_fp16:
        wf["5"] = {"inputs": {"control_net_name": CN, "device": cn_dev}, "class_type": "SaigaControlNetLoader"}
    elif cn_dev:
        wf["11"] = {"inputs": {"control_net": ["5", 0], "device": cn_dev}, "class_type": "SaigaControlNetDevice"}
        wf["6"]["inputs"]["control_net"] = ["11", 0]
    if vae_dev:
        wf["12"] = {"inputs": {"vae": ["1", 2], "device": vae_dev, "decode_mem_gb": vae_mem}, "class_type": "SaigaVAEDevice"}
        wf["9"]["inputs"]["vae"] = ["12", 0]
    if tiled:
        wf["9"] = {"inputs": dict(wf["9"]["inputs"], tile_size=tiled, overlap=64, temporal_size=64, temporal_overlap=8),
                   "class_type": "VAEDecodeTiled"}
    return wf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--prompt", default="a luminous crystal of the soul, sacred geometry, intricate facets, soft glow, dark background, highly detailed, art style")
    ap.add_argument("--negative", default="blurry, text, watermark, low quality")
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--cfg", type=float, default=2.5)
    ap.add_argument("--strength", type=float, default=0.85)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--out", default="/app/output/test.png")
    ap.add_argument("--cn-dev", default=""); ap.add_argument("--vae-dev", default=""); ap.add_argument("--clip-dev", default=""); ap.add_argument("--tiled", type=int, default=0); ap.add_argument("--cn-fp16", action="store_true"); ap.add_argument("--vae-mem", type=float, default=0.0)
    a = ap.parse_args()

    st, out = http("GET", "/system_stats")
    stats = json.loads(out)
    dev = stats["devices"][0]
    print(f"system_stats: {dev['name']} vram_total={dev['vram_total']//2**20} MiB free={dev['vram_free']//2**20} MiB")
    name, sub = upload(a.image)
    ref = f"{sub}/{name}" if sub else name
    print("uploaded:", ref)
    wf = workflow(a.prompt, a.negative, ref, a.seed, a.steps, a.cfg, a.size, a.size, a.strength, a.cn_dev, a.vae_dev, a.clip_dev, a.tiled, a.cn_fp16, a.vae_mem)
    t0 = time.time()
    st, out = http("POST", "/prompt", json.dumps({"prompt": wf, "client_id": "saiga-test"}).encode(),
                   {"Content-Type": "application/json"})
    pid = json.loads(out)["prompt_id"]
    print("prompt_id:", pid)
    while True:
        time.sleep(3)
        st, out = http("GET", f"/history/{pid}")
        h = json.loads(out)
        if pid in h:
            break
        if time.time() - t0 > 1800:
            print("TIMEOUT"); sys.exit(1)
    el = time.time() - t0
    entry = h[pid]
    status = entry.get("status", {})
    if status.get("status_str") == "error":
        print("ERROR:", json.dumps(status.get("messages", []))[:1500]); sys.exit(1)
    img = entry["outputs"]["10"]["images"][0]
    q = urllib.parse.urlencode({"filename": img["filename"], "type": img["type"], "subfolder": img.get("subfolder", "")})
    st, png = http("GET", f"/view?{q}", timeout=120)
    with open(a.out, "wb") as f:
        f.write(png)
    print(f"DONE in {el:.1f}s: {a.out} ({len(png)//1024} KB), steps={a.steps} cfg={a.cfg} size={a.size}")

if __name__ == "__main__":
    main()
