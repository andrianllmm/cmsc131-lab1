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

The three sections at the end of this file are yours. Complete Design Notes
and Subsystem Ownership before the Week 1 progress report. Complete Quirks
and Issues before the Week 3 progress report. Each section says what it
needs. Leave the rest of this file as it is.

## Fixtures

The provided files are fixtures. The grader compares your fork against the
starter. An edit to `driver.c`, `Makefile`, `run_tests.sh`,
`contract_test.c`, `contract_regs.asm`, or a provided `tests/` file appears
as a diff in the open. Your own headers and manifest lines are additions,
not edits.

---

## Design Notes

Complete this section before the Week 1 progress report. The syllabus asks
for problem analysis, a solution architecture, and an estimated timeline.
Keep each part short. Update it when the plan changes.

### Problem analysis

The tool reads a 20 byte IPv4 Header in network order, decodes it and stores those values in a 13 field struct, validates it thru checksum. Thru encoding it then writes a new 20 byte header using the values from the struct also in network order. Several fields are tightly packed (single byte or straddle byte boundary)

Header layout (20 bytes, network order)


| Bytes | Field | Explanation |
| -------- | -------- | -------- |
| 0 (top 4 bits)     | version   | IP version, always 4 bits  |
| 0 (low 4 bits)   | ihl   | header length, 32 bits = 4 bytes and max of 5 words since 20 bytes only   |
| 1 (top 6 bits)    | dscp   | A traffic priority system   |
| 1  (low 2 bits) | ecn   | Chceking if network is getting congested   |
| 2-3     | total_length   | Size of the whole packet (header and data) in bytes; In big-endian   |
| 4-5    | identification   | ID number for the packet so if packet was split, reassembly is possible   |
| 6   (top 3 bits)  | flags   | Control bit system for fragments   |
| 6-7  (low 5 bits + byte 7 ) | fragment_offset   | the position where this fragment's data belongs when reassembling the packet   |
| 8     | ttl   | router counter that prevents packets from looping forever    |
| 9    | protocol   | what is inside the payload and which handler to pass the data to  |
| 10-11     | checksum   | Validation, specifically detects corruption in the header   |
| 12-15    | source   | source of packets   |
| 16-19     | destination   | destination of packets   |


### Solution architecture

This project is split into three routines

- decode_header (decode.asm)
    - Fills the 13-field struct from the raw 20-byte header.
    - Reads multi-byte fields byte by byte and recombines them, so the network byte order never reaches a register unconverted.
    - Stores the checksum field as-is. It does not validate it; driver.c calls ip_checksum separately for the VALID line.
- encode_header (encode.asm)
    - does the reverse of decode; it rebuilds the 20-byte header from the field struct. Packs the different fields into its byte position. byte 0 gets the version and IHL, byte 1 gets DSCP and ECN, and the rest of the bit fields are broken into high and low bytes so they land in network order and their flags and offset are then carried by the bytes 6–7. Lastly, the checksum computes the value over the finished header thru its routine and its result is then stored back into the bytes 10-11.

- ip_checksum (checksum.asm)
    - Takes a pointer to the 20 byte header and its length.
    - Reads the header for every pair as 16-bit big-endian words.
    - Each word is a 32-bit accumulator, keeping the carries.
    - The high 16 bit value is one's complement and returned in AX.
    - The same routine is used for validation and encoding.
**Struct Offset**

| Offset | Field           |
|--------|-----------------|
| +0     | version         |
| +4     | ihl             |
| +8     | dscp            |
| +12    | ecn             |
| +16    | total_length    |
| +20    | identification  |
| +24    | flags           |
| +28    | fragment_offset |
| +32    | ttl             |
| +36    | protocol        |
| +40    | checksum        |
| +44    | src[0..3]       |
| +48    | dst[0..3]       |

### Decode Arguments

decode_header receives two cdecl arguments:

[ebp+8]  = unsigned char *hdr
[ebp+12] = struct ipv4_fields *out

### Checksum Arguments

ip_checksum receives two cdecl arguments:

[ebp+8]  = unsigned char *hdr
[ebp+12] = int len

The offsets come from the cdecl stack layout after the function creates
its stack frame with ENTER. The first argument is at EBP+8 and the
second argument is at EBP+12.

The checksum routine does not access the 13-field header struct directly.
It works on the raw 20-byte header pointed to by hdr.


**Register Plan**

| Register | Role         |
|--------|-----------------|
|EAX| 32-bit checksum accumulator; final checksum returned in AX   |
|EBX| Holds the second byte of the current 16-bit word |
|ECX| Remaining byte count |
|EDX| Temporary register for constructing a word and folding carries|
|ESI| Pointer to the current position in the header|
|EDI| Not used|
|EBP| Poiinter|





How the three routines split the work. Which registers each routine uses,
and how the struct offsets in `driver.c` map to the fields.

### Timeline

One line per week. Name the subsystem each week finishes and the member
who owns it.

| Week | Goal | Owner |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | Defense | |

## Subsystem Ownership

| Subsystem | Owner |
|---|---|
| Decode path (`decode.asm`) | Andrian Lloyd Maagma (andrianllmm) |
| Encode path (`encode.asm`) | John Romyr Lopez (romyr05) |
| Checksum and tests (`checksum.asm`, `tests/`) | Dejel De Asis (Dejely) |

## Quirks and Issues

Complete this section before the Week 3 progress report. The syllabus asks
for documentation of quirks and issues with the complete implementation.
One entry per item. State what happens, what causes it, and what the group
did about it.

### Known issues

-

### Quirks

-
