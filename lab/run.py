"""Lab runner: broker, optional capture, benign mix, and scheduled attacks. The schedule is written before the first packet.

python -m lab.run --out <dir> --plan episodes --episodes 6 --attack-s 40 --calm-s 25 --seed 0
python -m lab.run --out <dir> --plan benign --scenario qos_heavy --seconds 300
"""
import argparse
import json
import platform
import random
import socket
import subprocess
import threading
import time
from pathlib import Path

from . import attacks, benign, gateway, safety

DUMPCAP = r"C:\Program Files\Wireshark\dumpcap.exe"
TRAINED_FAMILIES = ("flood_connect", "flood_publish", "lowrate", "malformed", "bruteforce")


def make_schedule(episodes, attack_s, calm_s, seed, families=TRAINED_FAMILIES, lead_s=20):
    """Shuffled attack episodes with calm between, each from its own source, offsets in seconds from run start."""
    rng = random.Random(seed)
    order = [f for _ in range(episodes) for f in families]
    rng.shuffle(order)
    at, entries = lead_s, []
    for i, family in enumerate(order):
        entries.append({"episode": i, "family": family, "source": f"127.0.2.{(i % 200) + 10}", "start_s": at, "end_s": at + attack_s, "seed": seed * 1000 + i})
        at += attack_s + calm_s
    return entries, at


# Far below the rates in the training runs. Only for measuring where detection stops; never trained on.
STEALTH = {"flood_connect": {"rate": 5}, "flood_publish": {"rate": 100}, "lowrate": {"connections": 20, "ramp_per_s": 1}, "malformed": {"rate": 1}, "bruteforce": {"rate": 2}}


DEFAULT_OPTIONS = {"flood_connect": ("rate", 100, 2), "flood_publish": ("rate", 2000, 50), "malformed": ("rate", 20, 1), "bruteforce": ("rate", 30, 1), "wildcard": ("rate", 2, 1), "topic_probe": ("rate", 10, 1)}


def scaled_options(family, f):
    """Attack options at fraction f (0 < f <= 1) of each family's default rate, never above it, so the lab caps still hold."""
    if not 0 < f <= 1:
        raise ValueError("rate factor must be in (0, 1]")
    if family == "lowrate":
        return {"connections": max(6, round(120 * f)), "ramp_per_s": max(1, round(15 * f))}
    key, default, floor = DEFAULT_OPTIONS[family]
    return {key: max(floor, round(default * f))}


def varied_rates(schedule, seed):
    """Each episode at its own rate, log-uniform from 5% to 100% of the default, so a model cannot learn one script's rate."""
    rng = random.Random(seed)
    return [{**entry, "options": scaled_options(entry["family"], 10 ** rng.uniform(-1.3, 0))} for entry in schedule]


def ground_truth_writer(path):
    """Returns an on_marker callback. Starts with an empty list, so an alert in a benign run reads "no scheduled attack". Atomic, so the IDS never reads half a file."""
    path, marks = Path(path), []

    def write():
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(marks))
        temp.replace(path)

    def on_marker(mark):
        marks.append(mark)
        write()

    path.parent.mkdir(parents=True, exist_ok=True)
    write()
    return on_marker


def wait_for_port(port, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if not s.connect_ex(("127.0.0.1", port)):
                return True
        time.sleep(0.1)
    return False


def start_capture(path, port):
    command = [DUMPCAP, "-i", r"\Device\NPF_Loopback", "-f", f"tcp port {port}", "-w", str(path), "-q"]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)  # dumpcap has no ready signal, and packets before it starts would be lost
    if process.poll() is not None:
        raise RuntimeError("dumpcap did not start")
    return process


def devices_writer(ground_truth_path):
    """Writes the benign source -> profile map next to the ground truth, so the IDS can label topology nodes as scenario devices."""
    path = Path(ground_truth_path).with_name("devices.json")

    def write(sources):
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(sources))
        temp.replace(path)
    return write


def run(out, schedule, seconds, mix, port=1883, capture=True, scenario="episodes", on_marker=None, on_credentials=None, on_devices=None, attach=None):
    """attach: a lab.home state; the run then uses that already-running broker and its lab account instead of starting its own."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "schedule.json").write_text(json.dumps({"written_before_first_packet": True, "scenario": scenario, "mix": list(mix), "episodes": schedule, "seconds": seconds}, indent=1))
    broker_process, cred = (None, tuple(attach["lab"])) if attach else gateway.start_broker(out / "broker", port)
    broker = ("127.0.0.1", port)
    if on_credentials:
        on_credentials(cred)
    process = None
    try:
        if not wait_for_port(port):
            raise RuntimeError("broker did not start")
        process = start_capture(out / "capture.pcap", port) if capture else None
        stop = threading.Event()
        started_epoch = time.time()
        started = time.monotonic()
        threads, sources = benign.start(mix, stop, broker, cred)
        if on_devices:
            on_devices(sources)
        if scenario == "new_device":
            threading.Timer(seconds / 2, lambda: benign.start(("steady",), stop, broker, cred, base_host=100)).start()
        marks = []
        attack_threads = []
        for entry in schedule:
            delay = started + entry["start_s"] - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            mark = {**entry, "start_epoch": time.time(), "end_epoch": time.time() + entry["end_s"] - entry["start_s"]}
            marks.append(mark)
            if on_marker:
                on_marker(mark)
            t = threading.Thread(target=attacks.run_family, args=(entry["family"], entry["source"], entry["end_s"] - entry["start_s"], broker, cred, entry["seed"]), kwargs=entry.get("options", {}), daemon=True)
            t.start()
            attack_threads.append(t)
        remaining = started + seconds - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        stop.set()
        for t in attack_threads + threads:
            t.join(timeout=10)
        alive = broker_process.poll() is None if broker_process else wait_for_port(port, 1)
        (out / "manifest.json").write_text(json.dumps({
            "scenario": scenario, "started_epoch": started_epoch, "seconds": seconds, "episodes": marks, "benign_sources": sources,
            "broker_alive_at_end": alive, "platform": platform.platform(), "python": platform.python_version(),
            "lab": "windows-loopback, simulated clients; not a physical network or a Raspberry Pi"}, indent=1))
        return marks, sources
    finally:
        if process:
            process.terminate()
            process.wait(timeout=10)
        if broker_process:
            gateway.stop(broker_process)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--plan", choices=("episodes", "benign"), default="episodes")
    parser.add_argument("--episodes", type=int, default=6)
    parser.add_argument("--attack-s", type=int, default=40)
    parser.add_argument("--calm-s", type=int, default=25)
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--scenario", default="base")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--stealth", action="store_true")
    parser.add_argument("--vary-rates", action="store_true")
    parser.add_argument("--ground-truth", help="write attack start times here, for ids.service --schedule")
    parser.add_argument("--families", help="comma-separated attack families; default the five trained ones")
    parser.add_argument("--rate-factor", type=float, help="every episode at this fraction (0-1] of its default rate")
    parser.add_argument("--lead-s", type=int, default=20)
    parser.add_argument("--mix", help="extra benign devices as profile@device-id, comma-separated (the dashboard's Smart Home layout)")
    parser.add_argument("--attach", help="lab.home state file: use that running broker (the Wokwi smart home) instead of starting one")
    args = parser.parse_args()
    on_marker = ground_truth_writer(args.ground_truth) if args.ground_truth else None
    attach = json.loads(Path(args.attach).read_text()) if args.attach else None
    extra = [item.split("@", 1) for item in args.mix.split(",")] if args.mix else []
    if any(len(e) != 2 or e[0] not in benign.PROFILES or not e[1] or len(e[1]) > 12 for e in extra) or len(extra) > 24:
        parser.error("--mix takes at most 24 items of known_profile@device-id")
    mix = tuple(benign.SCENARIOS[args.scenario]) + tuple(p for p, _ in extra)
    labels = [None] * len(benign.SCENARIOS[args.scenario]) + [f"{p}@{i}" for p, i in extra]
    write = devices_writer(args.ground_truth) if args.ground_truth else None

    def label_devices(sources):
        """sources are the lab's own clients, in mix order: label each with its layout device, then keep the home's devices."""
        labelled = {s: labels[n] or p for n, (s, p) in enumerate(sources.items())}
        write({**(attach["devices"] if attach else {}), **labelled})
    on_devices = label_devices if write else None
    families = tuple(args.families.split(",")) if args.families else TRAINED_FAMILIES
    unknown = set(families) - set(attacks.FAMILIES)
    if unknown:
        parser.error(f"unknown families: {sorted(unknown)}")
    if args.plan == "episodes":
        schedule, seconds = make_schedule(args.episodes, args.attack_s, args.calm_s, args.seed, families, args.lead_s)
        if args.stealth:
            schedule = [{**entry, "options": STEALTH[entry["family"]]} for entry in schedule]
        if args.vary_rates:
            schedule = varied_rates(schedule, args.seed)
        if args.rate_factor:
            schedule = [{**entry, "options": scaled_options(entry["family"], args.rate_factor)} for entry in schedule]
        safety.check_caps(duration=args.attack_s)  # per episode; whole campaigns are longer by design
        run(args.out, schedule, seconds, mix, args.port, scenario=f"episodes-{args.scenario}", on_marker=on_marker, on_devices=on_devices, attach=attach)
    else:
        run(args.out, [], args.seconds, mix, args.port, scenario=args.scenario, on_marker=on_marker, on_devices=on_devices, attach=attach)


if __name__ == "__main__":
    main()
