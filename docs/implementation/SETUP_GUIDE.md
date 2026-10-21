# Setup Guide

> **Nothing in this guide has been executed yet.** Installing software changes your machine. Run these steps only after the team agrees on M1, and each person runs them on their own machine.

## 1. Current state of the shared laptop (inspected 2026-10-20)

| Item | Found |
|---|---|
| Project folder | `OneDrive/Documents/IOT project`, empty before the docs were added; **not a Git repository** |
| OS | Windows 11 |
| Python | `python` → 3.13.7; `pip` → Anaconda Python 3.12 (**two interpreters: use a venv to avoid confusion**) |
| Installed packages (Anaconda) | scikit-learn 1.8.0, pandas 2.3.3, numpy 2.3.3, psutil 5.9.0 |
| Node.js | v26.8.1 |
| Docker | not installed |
| Mosquitto, tshark, paho-mqtt | not installed |
| Claude Code plugins | Ponytail 5.2.0 (coding-style rules: smallest complete change; tests for non-trivial logic; `shortcut:` comments for known limits). It has no token-optimisation commands |

**OneDrive warning:** OneDrive syncing large PCAPs and `node_modules` is slow and can corrupt files that are written while syncing. Keep `data/` and `node_modules/` **outside** OneDrive, or exclude them from sync (Phase 01 decision D-05).

## 2. Repository initialisation (Phase 00, needs team approval)

```bash
# any OS, in the project root
git init
git add docs/ && git commit -m "docs: research and design baseline"
```

Recommended `.gitignore` entries: `data/`, `*.pcap`, `*.pcapng`, `.env`, `.venv/`, `node_modules/`, `results/**/*.joblib`.

## 3. Development environment (laptop)

**Recommended on Windows: WSL2 + Ubuntu 24.04.** tshark, Mosquitto, and the capture tools behave the same as on the Raspberry Pi.

```powershell
# Windows PowerShell (admin), once; requires a reboot
wsl --install -d Ubuntu-24.04
```

```bash
# inside WSL2 Ubuntu
sudo apt update
sudo apt install -y mosquitto mosquitto-clients tshark python3-venv
# tshark will ask whether non-root users may capture; answer "No" on shared machines,
# then capture with sudo, or add only your user to the wireshark group:
sudo usermod -aG wireshark "$USER"   # log out and back in
python3 -m venv .venv && . .venv/bin/activate
pip install scikit-learn pandas pyarrow psutil paho-mqtt fastapi uvicorn pyyaml joblib
pip freeze > requirements.lock.txt
```

## 4. Gateway (Raspberry Pi 4 4 GB / Pi 5)

```bash
# Raspberry Pi OS Lite 64-bit, wired Ethernet on the isolated lab switch
sudo apt update && sudo apt install -y mosquitto mosquitto-clients tshark python3-venv
python3 -m venv ~/edgewatch/.venv && . ~/edgewatch/.venv/bin/activate
pip install -r requirements.lock.txt   # same versions as the laptop (ADR-11)
# measurement settings (E3)
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
vcgencmd measure_temp; vcgencmd get_throttled
```

**Mosquitto lab configuration** (`/etc/mosquitto/conf.d/lab.conf`):

```conf
listener 1883 <GATEWAY_LAB_IP>   # bind to the lab interface only, never 0.0.0.0 on a connected network
allow_anonymous false
password_file /etc/mosquitto/passwd
log_type all
```

## 5. Dashboard toolchain

Node.js v26 is already present on the laptop. Scaffolding happens in Phase 05: `npm create vite@latest`, choosing TypeScript. Bundle fonts and libraries locally, because there is no internet in the lab.

## 6. Verification

| Check | Command | Expected |
|---|---|---|
| Broker | `mosquitto_sub -h <ip> -u lab -P <pw> -t test & mosquitto_pub -h <ip> -u lab -P <pw> -t test -m hi` | `hi` printed |
| tshark MQTT fields | `tshark -G fields \| grep -c "mqtt\."` | > 0; record the field names in FEATURE_SPECIFICATION §1 |
| Python | `python -c "import sklearn, paho.mqtt, psutil; print(sklearn.__version__)"` | Version printed |
