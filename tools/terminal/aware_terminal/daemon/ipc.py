from __future__ import annotations

import json
import struct
from typing import BinaryIO, Optional

from .models import ProtocolMessage

HEADER_SIZE = 4  # 32-bit length prefix


def encode_message(message: ProtocolMessage) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return struct.pack("!I", len(body)) + body


def decode_message(data: bytes) -> ProtocolMessage:
    payload = json.loads(data.decode("utf-8"))
    return payload  # type: ignore[return-value]


def read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            raise EOFError("Socket closed while reading message")
        chunks.extend(chunk)
    return bytes(chunks)


def read_message(stream: BinaryIO) -> ProtocolMessage:
    header = read_exact(stream, HEADER_SIZE)
    (length,) = struct.unpack("!I", header)
    payload = read_exact(stream, length)
    return decode_message(payload)


def write_message(stream: BinaryIO, message: ProtocolMessage) -> None:
    packet = encode_message(message)
    stream.write(packet)
    stream.flush()
