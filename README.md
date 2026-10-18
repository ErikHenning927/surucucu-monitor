# 🐍 Surucucu

<p align="center">
  <img src="assets/icon.svg" width="128" height="128" alt="Surucucu Logo" />
</p>

<p align="center">
  <b>Amazonian AI & Dev Observability Cockpit for Linux</b><br>
  <i>Inspirado na Surucucu (Lachesis muta): O predador ápice amazônico — rápido, silencioso e implacável.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/Platform-Linux%20(Wayland%20%2F%20X11)-FCC624?style=flat&logo=linux&logoColor=black" alt="Linux">
  <img src="https://img.shields.io/badge/UI-GTK3%20%2B%20Glassmorphic%20Cairo-4E9A06?style=flat&logo=gnome&logoColor=white" alt="GTK3">
  <img src="https://img.shields.io/badge/GPU-NVIDIA%20CUDA%20%2F%20VRAM-76B900?style=flat&logo=nvidia&logoColor=white" alt="NVIDIA">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat" alt="MIT License">
</p>

---

**Surucucu** é um cockpit HUD flutuante, translúcido e de alta performance desenvolvido especialmente para desenvolvedores, pesquisadores de Machine Learning e engenheiros de IA que rodam modelos locais, contêineres Docker e cargas de trabalho intensivas em GPU no Linux (GNOME / Wayland / X11).

---

## ⚡ Principais Recursos

### 🧠 1. VRAM & Inteligência Artificial
- **Alerta Preditivo de OOM (*Out Of Memory*)**:
  - 🟢 **Seguro** (< 70%)
  - 🟡 **Carga Alta** (70% - 87%)
  - 🔴 **RISCO CRÍTICO DE OOM** (≥ 88%): avisa antes de interromper runtimes do PyTorch, Ollama, vLLM ou ComfyUI.
- **Sparkline de VRAM em Tempo Real**: Histórico visual dos últimos 30 segundos com baseline visível.
- **Throughput PCIe e Barramento**: Monitoramento de leitura/escrita do barramento PCIe (TX/RX em MB/s) e % de utilização da memória de vídeo.
- **Detecção de Thermal Throttling**: Alerta imediato se a GPU ultrapassar temperaturas operacionais críticas (≥ 78°C).

### 🐳 2. Docker Streaming em Tempo Real
- **Worker Assíncrono com Zero Lag**: Atualização contínua sem travar a interface gráfica.
- **Inspeção de Contêineres**: Nomes amigáveis (`langfuse`, `pgvector`, `bot_telegram`, `api_gateway`, etc.), status, portas mapeadas (`:3000`, `:5432`, `:8000`), CPU % e consumo de RAM.
- **Ações Rápidas**: Reinicie (`docker restart`) ou pare (`docker stop`) qualquer contêiner com 1 clique direto no painel.

### 🔍 3. Classificação Inteligente de Processos
- Tags automáticas para rápida identificação:
  - `[CUDA C]`: Processo de computação direta na GPU (PyTorch, TensorFlow, Ollama).
  - `[GPU G]`: Processo gráfico/renderizador.
  - `[AI]`: Stack de Inteligência Artificial e bancos vetoriais.
  - `[Dev]`: Servidores de desenvolvimento (`uvicorn`, `vite`, `node`, `flask`).
  - `[Svc]`: Serviços e daemons em segundo plano.

### 🪟 4. Design Glassmorphic Dinâmico
- Estética moderna de vidro fosco com canal alfa dinâmico nativo no Wayland/GNOME.
- **Slider de Transparência (`🪟`)** de 15% a 100% diretamente no cabeçalho.
- Botão de fixação (**Pin / Always on Top**) para manter o cockpit visível durante o código.
- Preferências salvas automaticamente em `~/.config/surucucu/hud_config.json`.

---

## 🚀 Instalação e Uso

### Pré-requisitos (Linux / Ubuntu / Debian)

O Surucucu utiliza bibliotecas nativas do sistema para garantir overhead mínimo (< 0.5% CPU):

```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
```

### Instalação

#### ⚡ 1. Instalação Automática via `curl` (Recomendado)

Instale e configure tudo automaticamente no Linux (Ubuntu, Debian, Fedora, Arch) com um único comando:

```bash
curl -fsSL https://raw.githubusercontent.com/ErikHenning927/surucucu-monitor/main/install.sh | bash
```

> *O script instala as dependências gráficas nativas, baixa o pacote PyPI, configura o comando `surucucu` e adiciona o atalho e ícone oficial ao menu de aplicativos do sistema.*

#### 2. Via `pip` (PyPI)
```bash
pip install -U surucucu
```

#### 3. Instalação Local Editável (Desenvolvimento)
```bash
git clone https://github.com/ErikHenning927/surucucu-monitor.git
cd surucucu-monitor
pip install -e .
```

#### 2. Via `pipx` (Ambiente Isolado)
```bash
pipx install git+https://github.com/seu-usuario/surucucu.git
```

#### 3. Via `npx` (Node.js)
```bash
npx surucucu
```

---

## 🖥️ Comandos CLI

O comando `surucucu` fica disponível globalmente no seu terminal:

| Comando | Descrição |
| :--- | :--- |
| `surucucu` | Inicia o cockpit em primeiro plano |
| `surucucu -b`, `--background` | Inicia o cockpit em segundo plano |
| `surucucu --status` | Exibe se o cockpit está em execução e seu PID |
| `surucucu -r -b`, `--restart` | Reinicia a instância ativa em segundo plano |
| `surucucu -k`, `--stop` | Encerra com segurança as instâncias ativas |
| `surucucu -v`, `--version` | Exibe a versão instalada |

---

## 📂 Estrutura do Projeto

```
surucucu/
├── pyproject.toml              # Especificação moderna PEP 621 (pip / PyPI)
├── package.json                # Suporte a npm / npx
├── .gitignore                  # Regras de exclusão Git
├── bin/
│   └── surucucu.js             # Executável wrapper Node.js
├── src/
│   └── surucucu/
│       ├── __init__.py         # Metadados do pacote
│       ├── __main__.py         # Suporte a 'python3 -m surucucu'
│       ├── cli.py              # CLI e controle de lifecycle
│       ├── monitor.py          # Cockpit HUD GTK3 + Cairo
│       └── assets/             # Ícones SVG e PNG
├── surucucu.desktop            # Integração com o menu GNOME / Wayland
└── README.md                   # Documentação do projeto
```

---

## 📄 Licença

Distribuído sob a licença **MIT**. Consulte `LICENSE` ou `pyproject.toml` para obter mais detalhes.
