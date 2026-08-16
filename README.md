# ExeMiner

A desktop GUI tool for extracting the bundled contents of standalone Python executables — supports both **PyInstaller** and **Nuitka** builds. Comes with an optional Rust-accelerated scanner for faster processing on large onefile executables.

## What it does

Point ExeMiner at a compiled `.exe` and it unpacks whatever's inside it, using two different methodologies depending on how the exe was built.

---

## PyInstaller extraction methodology

PyInstaller onefile executables append a **CArchive** to the end of the original bootloader binary. The extractor works backward from the tail of the file:

1. **Find the cookie** — search the last chunks of the file (working backward in 8KB windows) for the magic marker `MEI\014\013\012\013\016`. This marks the start of the PyInstaller "cookie" structure.
2. **Read the cookie** — depending on whether the version is 2.0 or 2.1+ (detected by checking for the string `python` right after the cookie), unpack a struct containing: package length, TOC (table of contents) offset, TOC length, and the Python version used to build it.
3. **Compute the overlay** — the cookie gives us where the "overlay" (everything PyInstaller appended after the bootloader) starts and ends in the file.
4. **Parse the TOC** — the table of contents is a sequence of entries, each describing one bundled file: its position, compressed/uncompressed size, a compression flag, a type code (`s` = script/entry point, `M`/`m` = pyc module, `z`/`Z` = a PYZ archive, `d`/`o` = dependency metadata to skip), and its name.
5. **Extract each entry** — seek to each entry's position, read its bytes, `zlib.decompress()` if the compression flag is set, then write it out based on type:
   - `s` entries become `.pyc` files (the app's entry-point script)
   - `M`/`m` entries are already-compiled `.pyc` modules
   - `z`/`Z` entries are **PYZ archives** — a second layer of packaging (a zipped collection of marshalled bytecode) that gets recursively unpacked with `marshal.load()` on its own internal TOC
6. **Fix up bare `.pyc` headers** — PyInstaller sometimes strips the 16-byte `.pyc` header (magic number + flags + timestamp/hash) to save space. If the extractor never saw a real header elsewhere in the archive, it patches whatever magic bytes it *did* find onto every bare `.pyc` at the end, so they're valid enough to open with a decompiler.

The result is a full recovery of the original Python source's compiled bytecode and any bundled data files, without needing to run the exe at all.

## Nuitka extraction methodology

Nuitka onefile binaries don't have a documented archive format the way PyInstaller does — there's no public TOC struct to parse. Instead, extraction relies on **magic-header scanning** plus format-specific heuristics:

1. **Detect the container type** — read the first 4 bytes to tell if it's a Windows PE (`MZ`) or Linux ELF (`\x7fELF`).
2. **Narrow the search window** — rather than scanning the entire file (which can be hundreds of MB), only the last ~64MB is read, since Nuitka appends its payload near the end.
3. **PE-specific shortcut** — on Windows PEs, `pefile` is used to walk the resource directory and locate the `RT_RCDATA` resource with ID 27, which is where Nuitka commonly embeds its payload. If found, this gives a precise offset to probe instead of a blind scan.
4. **Magic-header scan** — regardless of the PE shortcut, the file is scanned for six known Nuitka payload markers: `KAX`, `KAY`, `NPKX`, `NPKY`, `NKAX`, `NKAY`. The `X`-suffixed headers mark a **raw** payload; the `Y`-suffixed ones mark a **zstd-compressed** payload. Every match becomes a "candidate" start offset.
5. **Try each candidate** — for every candidate offset, the extractor attempts to parse what follows as a stream of `(filename, size, data)` records:
   - Filenames are read as UTF-16LE (PE) or UTF-8 (ELF), null-terminated
   - An 8-byte little-endian size field follows
   - If compressed, a `zstandard` streaming decompressor sits in front of the read
   - Each candidate is first tried in **preview mode** (parse one record without writing anything) to cheaply reject false-positive header matches before committing to a real extraction
6. **Fallback to full-file scan** — if nothing is found in the last 64MB (e.g. an unusually large payload), the scan is retried against the entire file.

Because there's no authoritative index, this is fundamentally a best-effort/heuristic recovery — it works reliably against the container formats current Nuitka versions actually produce, but isn't a documented spec the way the PyInstaller CArchive is.

## Rust acceleration

The Nuitka header scan (step 4 above) is the hot path — it's a repeated `bytes.find()` loop searching for 6 different patterns across up to 64MB of data. On large executables this pure-Python loop is slow because it re-scans overlapping regions once per header.

The optional `exeminer_rust` module (built with PyO3 + the `memchr` crate) reimplements the same overlapping-match search in native code using SIMD-accelerated `memchr::memmem`. It's a drop-in replacement — same semantics, same output format — that the Python code calls first and falls back away from automatically if the module isn't built or isn't importable.

## Requirements

```
PyQt6>=6.6.0
qtawesome>=1.3.0
pefile>=2023.2.7
zstandard>=0.22.0
```

## Running it

```bash
pip install -r Requirements.txt
python main.py
```

## Building the Rust module (optional)

```bash
pip install maturin
cd rust_ext
maturin develop --release
```

If it's not built, the GUI just shows "Rust accel: off" and uses the pure-Python scanner instead — nothing breaks either way.
