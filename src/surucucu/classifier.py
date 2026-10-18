"""
Classificação heurística de processos locais e contêineres Docker (IA, Dev, Serviços).
"""

import re

# Palavras-chave associadas a ferramentas, frameworks, runtimes e bancos vetoriais de IA
AI_KEYWORDS = [
    "ollama", "llama", "vllm", "triton", "torch", "pytorch", "cuda",
    "transformers", "langchain", "langfuse", "langgraph", "chroma", "qdrant",
    "milvus", "weaviate", "pgvector", "gradio", "streamlit", "jupyter",
    "tensorrt", "onnx", "whisper", "diffusers", "autotrain", "deepspeed",
    "fastembed", "safetensors", "huggingface", "tgi", "mistral", "gemma",
    "worker", "agent", "sucuri", "suri", "gateway", "api_gateway", "bot_telegram",
    "litellm", "tempo", "grafana", "prometheus"
]

# Palavras-chave associadas a ambientes de desenvolvimento ativo
DEV_KEYWORDS = [
    "node", "npm", "npx", "yarn", "pnpm", "vite", "next", "webpack",
    "python", "python3", "flask", "django", "fastapi", "uvicorn", "gunicorn",
    "cargo", "rustc", "go", "java", "ruby", "php", "deno", "bun", "bot_"
]

# Palavras-chave associadas a serviços de sistema e daemons
SERVICE_KEYWORDS = [
    "systemd", "dockerd", "containerd", "postgres", "mysqld", "mariadb",
    "redis-server", "mongod", "nginx", "apache2", "cupsd", "bluetoothd",
    "avahi-daemon", "sshd", "snapd"
]

def is_ai_target(name, cmdline, ports="", image=""):
    """Verifica se o processo ou container pertence à stack de Inteligência Artificial."""
    name_l = name.lower()
    # Ignora navegadores e players de desktop comuns
    if any(ign in name_l for ign in ["spotify", "chrome", "chromium", "firefox", "brave", "edge", "discord", "slack", "teams", "gnome", "xorg", "wayland"]):
        return False
    # Limpa flags de navegador que causam falsos positivos (ex: --user-agent-product no Spotify)
    clean_cmd = re.sub(r'--user-agent[^\s]*', '', cmdline, flags=re.IGNORECASE)
    text = f"{name} {clean_cmd} {ports} {image}".lower()
    return any(k in text for k in AI_KEYWORDS)

def is_dev_target(name, cmdline, cwd, username):
    """Verifica se o processo pertence a um ambiente de desenvolvimento de software."""
    name_l = name.lower()
    cmd_l = cmdline.lower()
    is_user_home = "/home/" in cwd or "/home/" in cmd_l
    has_dev = any(k in name_l or f" {k}" in cmd_l or f"/{k}" in cmd_l for k in DEV_KEYWORDS)
    return (has_dev or is_user_home) and not name_l.startswith("gnome") and "antigravity" not in name_l

def is_service_target(name, cmdline, username):
    """Verifica se o processo é um serviço de infraestrutura ou daemon de segundo plano."""
    name_l = name.lower()
    cmd_l = cmdline.lower()
    return any(k in name_l or k in cmd_l for k in SERVICE_KEYWORDS) or username in ["root", "systemd", "postgres", "redis"]
