import torch
from diffusers import DiffusionPipeline

base_model = "black-forest-labs/FLUX.1-dev"
pipe = DiffusionPipeline.from_pretrained(base_model, torch_dtype=torch.bfloat16)

lora_repo = "prithivMLmods/Retro-Pixel-Flux-LoRA"
trigger_word = "Retro Pixel"
pipe.load_lora_weights(lora_repo)

device = torch.device("cpu")
pipe.to(device)
