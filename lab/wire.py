"""Minimal MQTT 3.1.1 packets and client over plain sockets, so the lab needs no third-party client. Lab traffic only."""
import socket
import struct

from .safety import check_target


def _varint(n):
    out = bytearray()
    while True:
        n, digit = n >> 7, n & 127
        out.append(digit | (128 if n else 0))
        if not n:
            return bytes(out)


def _str(text):
    data = text.encode() if isinstance(text, str) else text
    return struct.pack(">H", len(data)) + data


def packet(header, body=b""):
    return bytes([header]) + _varint(len(body)) + body


def connect(client_id, keepalive=60, user=None, password=None, clean=True, will=None):
    """will: (topic, payload, retain), sent by the broker at QoS 1 if this client vanishes without a DISCONNECT."""
    flags = (2 if clean else 0) | (0x80 if user else 0) | (0x40 if password else 0) | ((0x04 | 0x08 | (0x20 if will[2] else 0)) if will else 0)
    body = _str("MQTT") + b"\x04" + bytes([flags]) + struct.pack(">H", keepalive) + _str(client_id)
    if will:
        body += _str(will[0]) + _str(will[1])
    if user:
        body += _str(user)
    if password:
        body += _str(password)
    return packet(0x10, body)


def publish(topic, payload=b"", qos=0, retain=False, packet_id=1):
    return packet(0x30 | qos << 1 | int(retain), _str(topic) + (struct.pack(">H", packet_id) if qos else b"") + payload)


def subscribe(topic, qos=0, packet_id=1):
    return packet(0x82, struct.pack(">H", packet_id) + _str(topic) + bytes([qos]))


def unsubscribe(topic, packet_id=1):
    return packet(0xa2, struct.pack(">H", packet_id) + _str(topic))


PINGREQ = packet(0xc0)
DISCONNECT = packet(0xe0)


class Client:
    """One TCP connection from a chosen loopback source address. Reads only what the MQTT handshake needs."""

    def __init__(self, source, broker=("127.0.0.1", 1883), timeout=5.0):
        check_target(broker[0])
        self.sock = socket.socket()
        try:
            self.sock.settimeout(timeout)
            self.sock.bind((source, 0))
            self.sock.connect(broker)
        except OSError:
            self.sock.close()  # a refused connection must not leave the socket to the garbage collector
            raise
        self.next_id = 1

    def send(self, data):
        self.sock.sendall(data)

    def login(self, client_id, user=None, password=None, keepalive=60, will=None):
        """Send CONNECT and return the CONNACK code."""
        self.send(connect(client_id, keepalive, user, password, will=will))
        answer = self._read_exact(4)
        return answer[3]

    def _read_exact(self, n):
        data = b""
        while len(data) < n:
            part = self.sock.recv(n - len(data))
            if not part:
                raise ConnectionError("broker closed the connection")
            data += part
        return data

    def receive(self):
        """Read one whole packet: (first header byte, body)."""
        head = self._read_exact(1)[0]
        size, shift = 0, 0
        while True:
            byte = self._read_exact(1)[0]
            size |= (byte & 127) << shift
            shift += 7
            if not byte & 128:
                break
        return head, self._read_exact(size) if size else b""

    def _ack(self, wanted):
        """Read packets until the wanted type arrives; only needed for the QoS handshakes used here."""
        while True:
            head, _ = self.receive()
            if head >> 4 == wanted:
                return

    def publish(self, topic, payload=b"", qos=0, retain=False):
        pid = self.next_id
        self.next_id = pid % 65535 + 1
        self.send(publish(topic, payload, qos, retain, pid))
        if qos == 1:
            self._ack(4)
        elif qos == 2:
            self._ack(5)
            self.send(packet(0x62, struct.pack(">H", pid)))
            self._ack(7)

    def close(self, graceful=True):
        try:
            if graceful:
                self.send(DISCONNECT)
        except OSError:
            pass
        self.sock.close()
