"""Pin individual models of a workflow to another GPU (saiga homeserver, 2026-11-07).

The crystal workflow (SDXL Turbo + ControlNet canny) does not fit one 8 GB P104-100: ComfyUI keeps part of the
ControlNet in RAM and streams it every step. These nodes move ControlNet / VAE / text encoder to a second card,
leaving the main device to the SDXL UNet. Only activations cross the PCIe link.

Nodes take a loaded model and a device string ("cuda:1") and return the same model re-targeted; insert them between
the loader and its consumers. Unused device / single GPU -> no-op.
"""
import logging

import torch

import comfy.controlnet
import comfy.model_management as mm
import folder_paths

log = logging.getLogger("saiga_device")


def _move(obj, dev):
    if torch.is_tensor(obj):
        return obj.to(dev)
    if isinstance(obj, dict):
        return {k: _move(v, dev) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_move(v, dev) for v in obj)
    return obj


def _retarget(patcher, dev):
    """Point a ModelPatcher at dev; if it already sits loaded elsewhere, unload first (weights would be split)."""
    if patcher.load_device == dev:
        return False
    if any(lm.model is patcher for lm in mm.current_loaded_models):
        mm.unload_all_models()
    patcher.load_device = dev
    return True


def _device(name):
    dev = torch.device(name)
    if dev.type == "cuda" and (dev.index or 0) >= torch.cuda.device_count():
        log.warning("saiga_device: %s not available, keeping default device", name)
        return None
    return dev


DEVICE_INPUT = ("STRING", {"default": "cuda:1"})


class SaigaControlNetDevice:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"control_net": ("CONTROL_NET",), "device": DEVICE_INPUT}}

    RETURN_TYPES = ("CONTROL_NET",)
    FUNCTION = "apply"
    CATEGORY = "saiga"

    def apply(self, control_net, device):
        dev = _device(device)
        if dev is None or getattr(control_net, "_saiga_device", None) == dev:
            return (control_net,)
        _retarget(control_net.control_model_wrapped, dev)
        control_net.load_device = dev
        model = control_net.control_model
        forward = model.forward

        def forward_on_device(*args, **kwargs):
            # caller (ControlNet.get_control) builds inputs on the sampling device; run on ours, return to theirs
            back = kwargs["x"].device if "x" in kwargs else args[0].device
            out = forward(*_move(args, dev), **_move(kwargs, dev))
            return _move(out, back)

        model.forward = forward_on_device
        control_net._saiga_device = dev
        log.info("saiga_device: ControlNet -> %s", dev)
        return (control_net,)


class SaigaControlNetLoader(SaigaControlNetDevice):
    """ControlNetLoader that keeps weights in fp16 (Pascal otherwise stores them as fp32: 4.8 GB instead of 2.4 GB);
    compute still runs in fp32 via manual cast, same as the SDXL UNet. Then pins the model to `device`."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"control_net_name": (folder_paths.get_filename_list("controlnet"),), "device": DEVICE_INPUT}}

    FUNCTION = "load"

    def load(self, control_net_name, device):
        path = folder_paths.get_full_path_or_raise("controlnet", control_net_name)
        control_net = comfy.controlnet.load_controlnet(path, model_options={"dtype": torch.float16})
        return self.apply(control_net, device)


class SaigaVAEDevice:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"vae": ("VAE",), "device": DEVICE_INPUT},
                "optional": {"decode_mem_gb": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 64.0, "step": 0.25})}}

    RETURN_TYPES = ("VAE",)
    FUNCTION = "apply"
    CATEGORY = "saiga"

    def apply(self, vae, device, decode_mem_gb=0.0):
        dev = _device(device)
        if dev is not None:
            if _retarget(vae.patcher, dev):
                log.info("saiga_device: VAE -> %s", dev)
            vae.device = dev  # encode/decode move inputs to vae.device
        if decode_mem_gb > 0:
            # stock SDXL estimate for a 1024² fp32 decode is ~9 GB: on an 8 GB card that means weights loaded partially
            # (128 MB, streamed every call) and everything else evicted from the card. Real peak is far lower;
            # if it is ever exceeded, VAE.decode catches the OOM and retries tiled.
            vae.memory_used_decode = lambda shape, dtype, b=int(decode_mem_gb * 2**30): b
            vae.disable_offload = True  # VAE weights (~330 MB fp32) always fully on the card
        return (vae,)


class SaigaCLIPDevice:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"clip": ("CLIP",), "device": DEVICE_INPUT}}

    RETURN_TYPES = ("CLIP",)
    FUNCTION = "apply"
    CATEGORY = "saiga"

    def apply(self, clip, device):
        dev = _device(device)
        if dev is not None:
            if _retarget(clip.patcher, dev):
                log.info("saiga_device: CLIP -> %s", dev)
        return (clip,)


NODE_CLASS_MAPPINGS = {
    "SaigaControlNetDevice": SaigaControlNetDevice,
    "SaigaControlNetLoader": SaigaControlNetLoader,
    "SaigaVAEDevice": SaigaVAEDevice,
    "SaigaCLIPDevice": SaigaCLIPDevice,
}
