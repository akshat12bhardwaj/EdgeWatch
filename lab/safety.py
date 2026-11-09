"""Lab safety limits (handover section 12): attack traffic only reaches allow-listed targets, within rate and duration caps."""
import ipaddress
import os

MAX_RATE_PER_S = 5000
MAX_DURATION_S = 600
MAX_CONNECTIONS = 2000


class SafetyError(RuntimeError):
    pass


def allowed_targets():
    """Loopback is always allowed. Other addresses need LAB_TARGETS and must be private, so public brokers can never be listed."""
    extra = [a.strip() for a in os.environ.get("LAB_TARGETS", "").split(",") if a.strip()]
    for address in extra:
        if not ipaddress.ip_address(address).is_private:
            raise SafetyError("LAB_TARGETS may only list private addresses")
    return extra


def check_target(address):
    ip = ipaddress.ip_address(address)
    if not ip.is_loopback and address not in allowed_targets():
        raise SafetyError("target is not on the lab allow-list")


def check_caps(rate=0, duration=0, connections=0):
    if rate > MAX_RATE_PER_S or duration > MAX_DURATION_S or connections > MAX_CONNECTIONS:
        raise SafetyError("attack parameters exceed the lab caps")
