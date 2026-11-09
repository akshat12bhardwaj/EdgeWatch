"""Starts a lab Mosquitto broker from a generated config. The IDS never depends on this process, and this never touches the IDS."""
import os
import secrets
import shutil
import subprocess
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("EDGEWATCH_DATA", Path.home() / "edgewatch-data"))
TOOLS = DEFAULT_ROOT / "tools" / "mosquitto" / "Library"
LAB_USER = "labclient"


def find(tool, folder):
    return shutil.which(tool) or str(TOOLS / folder / f"{tool}.exe")


def start_broker(run_dir, port=1883, host="127.0.0.1"):
    """Returns (process, (user, password)). Credentials are random per run and stay in the run folder, outside Git."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    password = secrets.token_hex(12)
    passwords = run_dir / "lab.passwd"
    subprocess.run([find("mosquitto_passwd", "bin"), "-c", "-b", str(passwords), LAB_USER, password], check=True, capture_output=True)
    config = run_dir / "mosquitto.conf"
    config.write_text(f"listener {port} {host}\nallow_anonymous false\npassword_file {passwords.as_posix()}\npersistence false\n"
                      f"log_dest file {(run_dir / 'mosquitto.log').as_posix()}\nlog_type error\nlog_type warning\n")
    process = subprocess.Popen([find("mosquitto", "sbin"), "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process, (LAB_USER, password)


def stop(process, timeout=5):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
