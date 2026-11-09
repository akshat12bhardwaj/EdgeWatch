"""python -m dashboard.api [--host 127.0.0.1] [--port 8000]. Refuses to expose control beyond loopback without a token."""
import argparse
import ipaddress
import os

import uvicorn


def check_bind(host, token):
    if host != "localhost" and not ipaddress.ip_address(host).is_loopback and not token:
        raise SystemExit("set EDGEWATCH_API_TOKEN before binding beyond loopback")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    check_bind(args.host, os.environ.get("EDGEWATCH_API_TOKEN"))
    uvicorn.run("dashboard.api.app:app", host=args.host, port=args.port, log_level="warning")
