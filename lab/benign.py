"""Benign MQTT client profiles for the lab. Lab traffic is simulated, never a claim about real-world traffic."""
import threading
import time

from . import wire


def _publisher(source, stop, broker, cred, name, interval, qos=0, retain=False, burst=1, gap=0.0, reconnect_every=None, rng=None, size=0, vary_to=0):
    while not stop.is_set():
        try:
            c = wire.Client(source, broker)
            if c.login(name, *cred):
                return
            started = time.monotonic()
            n = 0
            while not stop.is_set():
                for _ in range(burst):
                    c.publish(f"sensor/{name}/{n % 4}", (b"%d" % n).ljust(rng.randint(size, vary_to) if vary_to and rng else size, b"."), qos=qos, retain=retain)
                    n += 1
                    if gap:
                        time.sleep(gap)
                # Long sleeps are split so stop is honoured, and pings keep the connection within its keep-alive.
                stop.wait(interval * (rng.uniform(0.8, 1.2) if rng else 1))
                if reconnect_every and time.monotonic() - started > reconnect_every:
                    break
            c.close()
        except OSError:
            stop.wait(1)


def _quiet(source, stop, broker, cred, name, ping_every=30):
    """Subscribes once, then only pings, like a display or actuator."""
    while not stop.is_set():
        try:
            c = wire.Client(source, broker)
            if c.login(name, *cred, keepalive=ping_every * 2):
                return
            c.send(wire.subscribe(f"sensor/{name}/cmd"))
            while not stop.wait(ping_every):
                c.send(wire.PINGREQ)
            c.close()
        except OSError:
            stop.wait(1)


def _holder(source, stop, broker, cred, name, keepalive=600, connections=2):
    """A legitimate device holding long connections with a large keep-alive and pinging within it, like a sleepy sensor."""
    held = []
    try:
        for i in range(connections):
            c = wire.Client(source, broker)
            if c.login(f"{name}-{i}", *cred, keepalive=keepalive):
                return
            held.append(c)
        while not stop.wait(min(keepalive / 2, 600)):
            for c in held:
                c.send(wire.PINGREQ)
    except OSError:
        pass
    finally:
        for c in held:
            c.close()


# name -> (worker, options). The E5 scenarios from EVALUATION_PROTOCOL section 4 are combinations of these.
PROFILES = {
    "steady": (_publisher, {"interval": 1.0}),
    "slow": (_publisher, {"interval": 10.0}),
    "bursty": (_publisher, {"interval": 8.0, "burst": 40, "gap": 0.01}),
    "qos1": (_publisher, {"interval": 0.5, "qos": 1}),
    "qos2": (_publisher, {"interval": 0.7, "qos": 2}),
    "retained": (_publisher, {"interval": 2.0, "retain": True}),
    "reconnecting": (_publisher, {"interval": 1.0, "reconnect_every": 12}),
    "quiet": (_quiet, {}),
    # Legitimate high-volume clients: a camera-like uploader and telemetry batches. Sizes differ between the two scenarios below.
    "telemetry_1k": (_publisher, {"interval": 1.0, "size": 1024}),
    "telemetry_4k": (_publisher, {"interval": 2.0, "size": 4096}),
    "uploader_32k": (_publisher, {"interval": 5.0, "size": 32768}),
    "telemetry_2k": (_publisher, {"interval": 1.0, "size": 2048}),
    "telemetry_8k": (_publisher, {"interval": 3.0, "size": 8192}),
    "uploader_64k": (_publisher, {"interval": 10.0, "size": 65536}),
    "chatty_20hz": (_publisher, {"interval": 0.05, "size": 64}),
    "chatty_50hz": (_publisher, {"interval": 0.02, "size": 32}),
    "hold_k300_c1": (_holder, {"keepalive": 300, "connections": 1}),
    "hold_k300_c3": (_holder, {"keepalive": 300, "connections": 3}),
    "hold_k450_c1": (_holder, {"keepalive": 450, "connections": 1}),
    "hold_k450_c3": (_holder, {"keepalive": 450, "connections": 3}),
    "hold_k600_c1": (_holder, {"keepalive": 600, "connections": 1}),
    "hold_k600_c3": (_holder, {"keepalive": 600, "connections": 3}),
    "hold_k900_c1": (_holder, {"keepalive": 900, "connections": 1}),
    "hold_k900_c3": (_holder, {"keepalive": 900, "connections": 3}),
    "hold_k1200_c1": (_holder, {"keepalive": 1200, "connections": 1}),
    "hold_k1200_c3": (_holder, {"keepalive": 1200, "connections": 3}),
    "hold_k1800_c1": (_holder, {"keepalive": 1800, "connections": 1}),
    "hold_k1800_c3": (_holder, {"keepalive": 1800, "connections": 3}),
    "hold_k3600_c1": (_holder, {"keepalive": 3600, "connections": 1}),
    "hold_k3600_c3": (_holder, {"keepalive": 3600, "connections": 3}),
    "hold_k7200_c1": (_holder, {"keepalive": 7200, "connections": 1}),
    "hold_k7200_c3": (_holder, {"keepalive": 7200, "connections": 3}),
    "hold_k30000_c1": (_holder, {"keepalive": 30000, "connections": 1}),
    "hold_k30000_c3": (_holder, {"keepalive": 30000, "connections": 3}),
    "varlen_small": (_publisher, {"interval": 0.5, "size": 10, "vary_to": 600}),
    "varlen_large": (_publisher, {"interval": 1.5, "size": 100, "vary_to": 6000}),
    "varlen_mid": (_publisher, {"interval": 1.0, "size": 20, "vary_to": 2500}),
    "varlen_fast": (_publisher, {"interval": 0.1, "size": 5, "vary_to": 300}),
    # Named smart-home devices (virtual, not real sensors). Never in any training run, so they test benign generalisation.
    "temp_humidity": (_publisher, {"interval": 5.0, "size": 24}),
    "motion": (_publisher, {"interval": 7.0, "burst": 3, "gap": 0.2, "qos": 1, "size": 8}),
    "light": (_publisher, {"interval": 15.0, "retain": True, "qos": 1, "size": 16}),
    "switch": (_publisher, {"interval": 20.0, "retain": True, "qos": 1, "size": 4, "reconnect_every": 120}),
    "door": (_publisher, {"interval": 12.0, "qos": 1, "size": 8}),
}
BASE_MIX = ("steady", "steady", "steady", "steady", "slow", "bursty", "qos1", "qos2", "retained", "reconnecting", "quiet", "quiet")
SCENARIOS = {
    "base": BASE_MIX,
    "steady_sensors": ("steady",) * 8 + ("slow",) * 4,
    "bursty_publishers": ("bursty",) * 8 + ("steady",) * 2,
    "qos_heavy": ("qos1",) * 5 + ("qos2",) * 5,
    "retained_churn": ("retained",) * 10,
    "reconnect_storm": ("reconnecting",) * 12,
    "heavy_train": ("telemetry_1k",) * 3 + ("telemetry_4k",) * 3 + ("uploader_32k",) * 2 + ("chatty_20hz",) * 2 + ("steady",) * 2,
    "heavy_test": ("telemetry_2k",) * 3 + ("telemetry_8k",) * 3 + ("uploader_64k",) * 2 + ("chatty_50hz",) * 2 + ("steady",) * 2,
    "heavy_train2": ("telemetry_1k", "telemetry_4k", "uploader_32k", "chatty_20hz", "steady", "qos1") + ("varlen_small",) * 3 + ("varlen_large",) * 3,
    "heavy_test2": ("telemetry_2k", "telemetry_8k", "uploader_64k", "chatty_50hz", "steady", "qos2") + ("varlen_mid",) * 3 + ("varlen_fast",) * 3,
    "hold_train": ("hold_k300_c1", "hold_k300_c3", "hold_k600_c1", "hold_k600_c3", "hold_k1200_c1", "hold_k1200_c3", "hold_k3600_c1", "hold_k3600_c3", "hold_k7200_c1", "steady", "steady", "qos1"),
    "hold_test": ("hold_k450_c1", "hold_k450_c3", "hold_k900_c1", "hold_k900_c3", "hold_k1800_c1", "hold_k1800_c3", "hold_k7200_c3", "hold_k30000_c1", "hold_k30000_c3", "steady", "steady", "qos2"),
    "smart_home": ("temp_humidity",) * 4 + ("motion",) * 2 + ("light",) * 2 + ("switch",) * 2 + ("door", "quiet"),
    "new_device": ("steady",) * 6,  # new_device_at joins one more client later
    "wokwi_only": (),  # no Python clients: the Wokwi ESP32 on the lab.home broker is the only normal device
    "layout": (),  # only the devices passed with lab.run --mix (the dashboard's Smart Home layout)
}


def start(mix, stop, broker, cred, base_host=10):
    """Start one thread per client, each from its own loopback address. Returns (threads, {source address: profile})."""
    import random
    threads, sources = [], {}
    for i, profile in enumerate(mix):
        source = f"127.0.1.{base_host + i}"
        worker, options = PROFILES[profile]
        extra = {"rng": random.Random(i)} if worker is _publisher else {}
        t = threading.Thread(target=worker, args=(source, stop, broker, cred, f"{profile}{i}"), kwargs={**options, **extra}, daemon=True)
        t.start()
        threads.append(t)
        sources[source] = profile
    return threads, sources
