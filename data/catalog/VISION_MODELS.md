# Local vision models (BAMBAM)

Found on `/Volumes/BAMBAM/MODELS`:

| Model | Path | Backend tip |
|-------|------|-------------|
| **Qwen2.5-VL-7B-Instruct** Q4_K_M | `lmstudio-community/Qwen2.5-VL-7B-Instruct-GGUF/` (+ `mmproj-model-f16.gguf`) | LM Studio / llama.cpp vision |
| **GLM-4.6V-Flash** MLX 4bit | `lmstudio-community/GLM-4.6V-Flash-MLX-4bit/` | LM Studio MLX (Apple Silicon) |
| Gemma-4 / Qwen3.6 text | same folder | text triage, not vision |

Ollama manifests present: `qwen3-embedding:8b`, `llama3.2:3b` (not vision).

Recommended for formation triage:
```bash
# Start LM Studio, load Qwen2.5-VL-7B or GLM-4.6V-Flash, enable local server :1234
cd /Users/perbrinell/Documents/TIN-STUDY/crop-circles
source .venv/bin/activate
# Model IDs as exposed by LM Studio /v1/models (2026-07-25):
python tools/ccat/vision_probe.py data/images/chualar_2013_nvidia_hoax.png \
  --backend lmstudio --model "qwen/qwen2.5-vl-7b"
# alt: --model "zai-org/glm-4.6v-flash"
```

B8 outputs: `outputs/vision/*_qwen.json` (geometry-only prompt).