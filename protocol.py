# ISKOMENTARISANO: UDP protokol (header + payload)
# protocol.py
import struct
import time

# B B B B I H H Q H H = 24 bajta headerea
HEADER_FORMAT = "!BBBBIHHQHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

PROTOCOL_VERSION = 1

FLAG_KEY_FRAME = 0x01      # primjer za flag
CODEC_JPEG = 1             # 1 = JPEG


def calc_checksum(data: bytes) -> int:
    """
    Jednostavan checksum – suma bajtova mod 65535.
    """
    return sum(data) % 65535


def build_packet(
    frame_id: int,
    fragment_id: int,
    total_fragments: int,
    payload: bytes,
    *,
    codec: int = CODEC_JPEG,
    flags: int = 0,
    timestamp_ms: int | None = None,
) -> bytes:
    """
    Gradi (header + payload) za jedan fragment frejma.
    Kod UDP-a koristimo fragmentaciju, pa šaljemo više ovih paketa za jedan frame.
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload mora biti bytes ili bytearray")

    payload_size = len(payload)
    if payload_size > 65535:
        raise ValueError("payload prevelik za uint16 (maks 65535)")

    checksum = calc_checksum(payload)

    header = struct.pack(
        HEADER_FORMAT,
        PROTOCOL_VERSION,  # version
        flags,             # flags
        codec,             # codec
        0,                 # reserved
        frame_id,
        fragment_id,
        total_fragments,
        timestamp_ms,
        payload_size,
        checksum,
    )

    return header + payload


def parse_packet(packet: bytes) -> tuple[dict, bytes]:
    """
    Parsira (header + payload) paket.
    Vraća (header_dict, payload_bytes) ili baca ValueError ako je nešto neispravno.
    """
    if len(packet) < HEADER_SIZE:
        raise ValueError("Paket prekratak")

    header_part = packet[:HEADER_SIZE]
    payload = packet[HEADER_SIZE:]

    (
        version,
        flags,
        codec,
        reserved,
        frame_id,
        fragment_id,
        total_fragments,
        timestamp_ms,
        payload_size,
        checksum,
    ) = struct.unpack(HEADER_FORMAT, header_part)

    if version != PROTOCOL_VERSION:
        raise ValueError(f"Nepodržana verzija protokola: {version}")

    if payload_size != len(payload):
        raise ValueError("payload_size ne odgovara dužini payloada")

    if calc_checksum(payload) != checksum:
        raise ValueError("Neispravan checksum – korumpiran paket")

    header = {
        "version": version,
        "flags": flags,
        "codec": codec,
        "frame_id": frame_id,
        "fragment_id": fragment_id,
        "total_fragments": total_fragments,
        "timestamp_ms": timestamp_ms,
        "payload_size": payload_size,
    }

    return header, payload
