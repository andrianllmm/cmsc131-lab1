#!/usr/bin/env python3

from pathlib import Path
import re
import struct
import subprocess


ROOT = Path(__file__).resolve().parent.parent

BIN_DIR = ROOT / "tests"
EXPECTED_DIR = BIN_DIR / "expected"
MANIFEST = BIN_DIR / "manifest.txt"

TEMPLATE_BIN = BIN_DIR / "sample01.bin"
TEMPLATE_OUT = EXPECTED_DIR / "sample01.out"


def checksum(header: bytearray) -> int:
    """Calculate the IPv4 header checksum."""
    total = 0

    for i in range(0, len(header), 2):
        word = (header[i] << 8) | header[i + 1]
        total += word

    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def set_field(output: str, label: str, value: str) -> str:
    """
    Replace the value after a field label while preserving the
    original spacing. This keeps values aligned at column 19.
    """
    pattern = rf"^({re.escape(label)}\s+).*$"

    match = re.search(pattern, output, flags=re.MULTILINE)

    if not match:
        raise RuntimeError(f"Could not find field: {label}")

    prefix = match.group(1)

    # Ensure the value starts at column 19.
    value_column = len(prefix) + 1
    if value_column != 19:
        raise RuntimeError(
            f"{label} starts at column {value_column}, not column 19"
        )

    replacement = f"{prefix}{value}"

    return re.sub(
        pattern,
        replacement,
        output,
        count=1,
        flags=re.MULTILINE,
    )


def build_header(template: bytes, total_length=None, ttl=None,
                 dscp=None, ecn=None) -> bytearray:
    """Modify selected IPv4 fields in the template header."""
    header = bytearray(template)

    # DSCP + ECN share byte 1.
    if dscp is not None or ecn is not None:
        current_dscp = header[1] >> 2
        current_ecn = header[1] & 0x03

        if dscp is None:
            dscp = current_dscp

        if ecn is None:
            ecn = current_ecn

        header[1] = (dscp << 2) | ecn

    # Total Length = bytes 2-3, network byte order.
    if total_length is not None:
        struct.pack_into(">H", header, 2, total_length)

    # TTL = byte 8.
    if ttl is not None:
        header[8] = ttl

    # Recalculate checksum.
    header[10] = 0
    header[11] = 0

    csum = checksum(header)
    struct.pack_into(">H", header, 10, csum)

    return header


def build_expected(template_output: str, header: bytes) -> str:
    """Update the expected output while preserving its exact formatting."""

    # Decode the values directly from the generated header.
    total_length = (header[2] << 8) | header[3]
    dscp = header[1] >> 2
    ecn = header[1] & 0x03
    ttl = header[8]
    csum = (header[10] << 8) | header[11]

    output = template_output

    output = set_field(output, "DSCP:", str(dscp))
    output = set_field(output, "ECN:", str(ecn))
    output = set_field(output, "Total Length:", str(total_length))
    output = set_field(output, "TTL:", str(ttl))
    output = set_field(output, "Header Checksum:", f"0x{csum:04X}")

    return output


def add_test(name: str, **changes):
    binary_template = TEMPLATE_BIN.read_bytes()
    output_template = TEMPLATE_OUT.read_text()

    header = build_header(binary_template, **changes)

    if len(header) != 20:
        raise RuntimeError(f"{name}: header is {len(header)} bytes, expected 20")

    binary_path = BIN_DIR / f"{name}.bin"
    output_path = EXPECTED_DIR / f"{name}.out"

    binary_path.write_bytes(header)
    output_path.write_text(build_expected(output_template, header))

    return binary_path, output_path


def add_manifest_entry(name: str):
    line = f"{name} valid"

    existing = MANIFEST.read_text() if MANIFEST.exists() else ""
    lines = existing.splitlines()

    if line not in lines:
        with MANIFEST.open("a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(line + "\n")


def main():
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    tests = {
        "len20": {
            "total_length": 20,
        },
        "len65535": {
            "total_length": 65535,
        },
        "ttl1": {
            "ttl": 1,
        },
        "ttl255": {
            "ttl": 255,
        },
        "dscp63_ecn3": {
            "dscp": 63,
            "ecn": 3,
        },
    }

    print("Creating boundary tests...\n")

    for name, changes in tests.items():
        binary_path, output_path = add_test(name, **changes)
        add_manifest_entry(name)

        print(f"  created {binary_path.relative_to(ROOT)}")
        print(f"  created {output_path.relative_to(ROOT)}")
        print(f"  added   {name} valid")

    print("\nDone.")


if __name__ == "__main__":
    main()
