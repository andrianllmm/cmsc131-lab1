<!--no-pdf-->
# CMSC 131 Lab 1 Starter

Decode, encode, and checksum 20-byte IPv4 packet headers under a C driver.
The manual is the assignment. This file is the repository's own notes.

## Layout

```text
Makefile            platform preamble and build rules
driver.c            provided: argument parsing and file I/O
cdecl.h             provided: the calling-convention macros
decode.asm          yours
encode.asm          yours
checksum.asm        yours
run_tests.sh        provided: the correctness gate
contract_test.c     provided: the second pass, in C
contract_regs.asm   provided: register discipline checks for contract_test
tests/              provided: the header fixtures, their expected output,
                    and manifest.txt, the list both passes read
LICENSE             CC BY-NC-SA 4.0, inherited from the pcasm material
```

## What to Run

```bash
make
make check
```

`make` builds `renpkt` and `contract_test`. `make check` builds both, then
runs `./run_tests.sh`, which reports each test and exits nonzero when any
of them differ.

The gate has two passes. The first decodes every header listed in
`tests/manifest.txt` and compares the output with `tests/expected/`. The
second is `contract_test`. It decodes and re-encodes every header the
manifest marks valid. It checks a checksum vector that needs the carry
folded twice. It checks that all three routines keep `ebx`, `esi`, `edi`,
and `ebp`, and return with `esp` where the call left it. A program can pass
the first pass and fail the second. That failure is the usual encoder bug.

## Reading a First Run

The assembly files ship as stubs that assemble and link as-is, so the build
works before you write any code. Right now they do nothing useful, which
makes every check fail: `7 of 7 checks differ`. That red run is the correct
starting state for a starter. The badge stays red until you implement the
routines.

## Adding a Header

Put the header in `tests/NAME.bin`. Write the output `renpkt --decode`
must print for it in `tests/expected/NAME.out`. Then add one line to
`tests/manifest.txt`:

```text
NAME valid
```

Use `invalid` for a header with a wrong checksum. A valid header joins the
round trip in `contract_test` as well as the decode pass. The gate fails
and names the file when a `.bin` is not in the manifest, and when a listed
header has no expected file.

## The Driver's Argument Checks

`renpkt --encode` refuses a value its field cannot hold, and two values the
standard forbids. `--len` takes 20 through 65535, because the total length
counts the header. It defaults to 20. `--flags` takes 0 through 3, because
the top bit of the field is reserved and must be zero. `--df` sets 2 and
`--mf` sets 1. A refused option exits with status 2 and writes no file.

## Documentation

## Fixtures

The provided files are fixtures. The grader compares your fork against the
starter. An edit to `driver.c`, `Makefile`, `run_tests.sh`,
`contract_test.c`, `contract_regs.asm`, or a provided `tests/` file appears
as a diff in the open. Your own headers and manifest lines are additions,
not edits.

---

## Design Notes

### Problem analysis

The tool reads a 20-byte IPv4 header in network order, decodes it and stores those values in a 13-field struct, validates it through checksum. Through encoding it then writes a new 20-byte header using the values from the struct also in network order. Several fields are tightly packed (single byte or straddle byte boundary).

#### Header layout (20 bytes, network order)

| Bytes | Field | Explanation |
|---|---|---|
| 0 (top 4 bits) | version | IP version, 4-bit field, always 4 for IPv4 |
| 0 (low 4 bits) | ihl | header length in 32-bit (4-byte) words, 4-bit field (max 15), always 5 here (20 bytes) |
| 1 (top 6 bits) | dscp | A traffic priority system |
| 1 (low 2 bits) | ecn | Checking if network is getting congested |
| 2-3 | total_length | Size of the whole packet (header and data) in bytes; In big-endian |
| 4-5 | identification | ID number for the packet so if packet was split, reassembly is possible |
| 6 (top 3 bits) | flags | Control bit system for fragments |
| 6-7 (low 5 bits + byte 7) | fragment_offset | the position where this fragment's data belongs when reassembling the packet |
| 8 | ttl | router counter that prevents packets from looping forever |
| 9 | protocol | what is inside the payload and which handler to pass the data to |
| 10-11 | checksum | Validation, specifically detects corruption in the header |
| 12-15 | source | source of packets |
| 16-19 | destination | destination of packets |

### Solution architecture

#### Overview

This project is split into three routines: `decode_header` (`decode.asm`),
`encode_header` (`encode.asm`), and `ip_checksum` (`checksum.asm`).

#### Calling convention

The offsets come from the cdecl stack layout after the function creates
its stack frame with ENTER. The first argument is at EBP+8 and the
second argument is at EBP+12.

#### Struct offsets

| Offset | Field |
|---|---|
| +0 | version |
| +4 | ihl |
| +8 | dscp |
| +12 | ecn |
| +16 | total_length |
| +20 | identification |
| +24 | flags |
| +28 | fragment_offset |
| +32 | ttl |
| +36 | protocol |
| +40 | checksum |
| +44 | src[0..3] |
| +48 | dst[0..3] |

#### `decode_header` (`decode.asm`)

- Fills the 13-field struct from the raw 20-byte header.
- Reads multi-byte fields byte by byte and recombines them, so the network byte order never reaches a register unconverted.
- Stores the checksum field as-is. It does not validate it; driver.c calls ip_checksum separately for the VALID line.

##### Arguments

decode_header receives two cdecl arguments:

```text
[ebp+8]  = unsigned char *hdr
[ebp+12] = struct ipv4_fields *out
```

#### `encode_header` (`encode.asm`)

- Does the reverse of decode: rebuilds the 20-byte header from the field struct.
- Packs byte 0 with the version and IHL, and byte 1 with DSCP and ECN.
- Splits multi-byte fields into high and low bytes, so they land in network order.
- Packs the flags and fragment offset into bytes 6-7.
- Computes the checksum last, over the finished header, via `ip_checksum`, and stores the result in bytes 10-11.

##### Arguments

encode_header receives two cdecl arguments:

```text
[ebp+8]  = struct ipv4_fields *in
[ebp+12] = unsigned char *hdr
```

#### `ip_checksum` (`checksum.asm`)

- Takes a pointer to the 20-byte header and its length.
- Reads the header two bytes at a time as 16-bit big-endian words.
- Adds each word to a 32-bit accumulator, keeping the carries.
- Folds the carries back in until the sum fits in 16 bits, then returns its one's complement (NOT) in AX.
- Serves both validation and encoding with the same routine.
- Works on the raw 20-byte header only. It does not access the 13-field struct.

##### Arguments

ip_checksum receives two cdecl arguments:

```text
[ebp+8]  = unsigned char *hdr
[ebp+12] = int len
```

### Timeline

| Week | Goal | Owner |
|---|---|---|
| 1 | Write the design notes and split the subsystems | All |
| 1 | Decode prototype that reads the version and IHL | Andrian Lloyd Maagma |
| 2 | Decode all thirteen fields on every sample | Andrian Lloyd Maagma |
| 2 | Checksum that detects the corrupted sample | Dejel De Asis |
| 2 | Encoder clears the checksum field before computing it | John Romyr Lopez |
| 3 | Encode a header that matches the original byte for byte | John Romyr Lopez |
| 3 | Add our own test headers and pass every check | Dejel De Asis |
| 3 | Document quirks and issues | All |
| 4 | Defend the project | All |

## Subsystem Ownership

| Subsystem | Owner |
|---|---|
| Decode path (`decode.asm`) | Andrian Lloyd Maagma (andrianllmm) |
| Encode path (`encode.asm`) | John Romyr Lopez (romyr05) |
| Checksum and tests (`checksum.asm`, `tests/`) | Dejel De Asis (Dejely) |

## Quirks and Issues

One entry per item: what happens, what causes it, and what the group did
about it.

### Known issues

- **A plain 16-bit load reverses a multi-byte field.** Loading bytes 2-3
  with a single `mov ax, [esi+2]` gives the field byte-swapped, because the
  header is big-endian and x86 is little-endian. The total length `0x0014`
  comes back as `0x1400`. Both paths read every multi-byte field one byte
  at a time and recombine with a shift and an `or`, so network order never
  reaches a register unconverted.

- **The checksum field has to be zero while the checksum is computed.**
  Encoding the real checksum into bytes 10-11 and then summing the header
  folds that value into its own result, so the header no longer validates.
  The encoder writes bytes 10-11 as zero first, calls `ip_checksum` over
  the finished header, and only then stores the 16-bit result.

- **The encoder must not copy the struct's checksum member.** The struct
  carries the checksum that decode read, but encode recomputes it. Copying
  `+40` into the output would reintroduce the stored value and defeat the
  zero-then-compute step. Encode skips `+40` on purpose and computes
  instead.

- **The two routines take their pointers in opposite stack slots.** Decode
  has `hdr` at `[ebp+8]` and the struct at `[ebp+12]`; encode has the
  struct at `[ebp+8]` and `hdr` at `[ebp+12]`. Wiring `esi`/`edi` the same
  way in both silently reads and writes the wrong buffer. Each file loads
  the pointers per its own contract, and `contract_test` catches a mismatch.

- **`ip_checksum` returns the carry fold, which can run twice.** Adding the
  ten words of a full header into a 32-bit accumulator can overflow 16 bits
  by more than one carry, and a single fold still leaves a value above
  `0xFFFF`. The fold loops on `cmp eax, 0xFFFF / ja` until the sum fits,
  then takes the one's complement. The manual's worked vector (`0x9CBC`)
  is the test.

### Quirks

- **A stub build is supposed to fail every check.** `checksum.asm` ships
  returning 0, which reports every header VALID, and `encode.asm` writes
  nothing, so the output is whatever the buffer held. A fresh `make check`
  prints `7 of 7 checks differ`. That red run is the correct starting
  state, not a broken toolchain.

- **Exported names are spelled differently per platform.** Windows C
  prefixes every exported symbol with an underscore and Linux C does not.
  The Makefile passes `-d ELF_TYPE` on Linux, and the `%ifdef ELF_TYPE`
  block at the top of each `.asm` respells `_decode_header`,
  `_encode_header`, and `_ip_checksum` to match. The block is left alone.

- **`checksum.asm` preserves `eax` across its epilogue.** It saves `ebx`
  and `esi` with `push`/`pop` rather than `pusha`, so the answer already
  sits in `ax` before the pops and the pops restore only `esi`/`ebx`.
  Folding or popping after the result is placed would overwrite it.

- **Four-bit fields occupy a full four-byte int in the struct.** Version,
  IHL, DSCP, and ECN are nibble- or two-bit-wide on the wire but each take
  a 4-byte `int` slot in the struct, so decode stores a full dword for a
  field that is two bits wide. The wire width only reappears when encode
  masks the field back down before packing the byte.

- **The driver rejects out-of-range options with exit status 2 and writes
  no file.** `--len` takes 20 through 65535 (the total length counts the
  20-byte header), and `--flags` takes 0 through 3 because the top bit of
  the field is reserved and must be zero. A refused option never reaches
  the encoder.
