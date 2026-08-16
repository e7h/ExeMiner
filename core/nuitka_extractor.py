
import os
import struct
import io
try:
    import pefile
except ImportError:
    pefile = None
try:
    import zstandard as zstd
except ImportError:
    zstd = None
try:
    import exeminer_rust
    RUST_ACCEL_AVAILABLE = True
except ImportError:
    exeminer_rust = None
    RUST_ACCEL_AVAILABLE = False

MAGIC_HEADERS = [b"KAX", b"KAY", b"NPKX", b"NPKY", b"NKAX", b"NKAY"]
MAX_FILENAME_CHARS = 4096
MAX_FILES_TO_TRY = 20000
MAX_BYTES_TO_SCAN_FROM_END = 64 * 1024 * 1024

def _scan_for_headers(data):

    if RUST_ACCEL_AVAILABLE:
        try:
            return exeminer_rust.find_headers(data, MAGIC_HEADERS)
        except Exception:
            pass  

    results = []
    for h in MAGIC_HEADERS:
        off = 0
        while True:
            idx = data.find(h, off)
            if idx == -1:
                break
            results.append((idx, h))
            off = idx + 1
    results.sort(key=lambda x: x[0])
    return results


def detect_file_type(path):
    with open(path, "rb") as f:
        head = f.read(4)
    if head.startswith(b"MZ"):
        return "PE"
    if head == b"\x7fELF":
        return "ELF"
    return None


def locate_rcdata_end_pe(path):

    if pefile is None:
        return None
    try:
        pe = pefile.PE(path, fast_load=False)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
        if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
            return None
        RT_RCDATA = 10
        TARGET_ID = 27
        for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if getattr(entry, "id", None) != RT_RCDATA:
                continue
            for sub in getattr(entry, "directory", {}).entries:
                if getattr(sub, "id", None) != TARGET_ID:
                    continue
                for lang in getattr(sub.directory, {}).entries:
                    ds = getattr(lang.data, "struct", None)
                    if ds:
                        offset = getattr(ds, "OffsetToData", None)
                        size = getattr(ds, "Size", None)
                        if offset is not None and size is not None:
                            file_offset = pe.get_offset_from_rva(offset)
                            pe.close()
                            return int(file_offset + size)
    except Exception:
        pass
    return None


def try_extract_from_stream(stream, file_type, outdir_base, preview_only=False):

    def _read_exact(n):
        data = bytearray()
        while len(data) < n:
            chunk = stream.read(n - len(data))
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    def read_filename():
        if file_type == "PE":
            name_bytes = bytearray()
            chars = 0
            while True:
                pair = _read_exact(2)
                if not pair or pair == b"\x00\x00":
                    break
                name_bytes.extend(pair)
                chars += 1
                if chars > MAX_FILENAME_CHARS:
                    return None
            try:
                return name_bytes.decode("utf-16le")
            except Exception:
                return name_bytes.decode("latin-1", errors="replace")
        else:
            arr = bytearray()
            chars = 0
            while True:
                b = _read_exact(1)
                if not b or b == b"\x00":
                    break
                arr.extend(b)
                chars += 1
                if chars > MAX_FILENAME_CHARS:
                    return None
            try:
                return arr.decode("utf-8", errors="replace")
            except Exception:
                return arr.decode("latin-1", errors="replace")

    files_extracted = 0
    outdir = outdir_base
    if not preview_only:
        os.makedirs(outdir, exist_ok=True)

    for _ in range(MAX_FILES_TO_TRY):
        fn = read_filename()
        if fn is None or fn == "":
            break
        if file_type == "ELF":
            _ = _read_exact(1)
        size_buf = _read_exact(8)
        if not size_buf or len(size_buf) != 8:
            break
        file_size = struct.unpack("<Q", size_buf)[0]
        if file_size < 0 or file_size > 10 * 1024 * 1024 * 1024:
            break

        if preview_only:
            return True, 1

        safe_fn = fn.replace("..", "__")
        outpath = os.path.join(outdir, safe_fn)
        os.makedirs(os.path.dirname(outpath), exist_ok=True)
        remaining = file_size
        try:
            with open(outpath, "wb") as outf:
                while remaining > 0:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    outf.write(chunk)
                    remaining -= len(chunk)
            if remaining != 0:
                os.remove(outpath)
                break
            files_extracted += 1
        except Exception:
            try:
                os.remove(outpath)
            except Exception:
                pass
            break

    return (files_extracted > 0), files_extracted


def attempt_at_candidate(data_bytes, candidate_index, header_bytes, file_type, outdir_base):

    start = candidate_index + len(header_bytes)
    remaining_bytes = data_bytes[start:]
    bio = io.BytesIO(remaining_bytes)
    compressed = header_bytes in (b"KAY", b"NPKY", b"NKAY")

    if compressed:
        if zstd is None:
            return False, 0, "Compressed payload but zstandard not installed"
        try:
            dctx = zstd.ZstdDecompressor()
            reader = dctx.stream_reader(bio)
        except Exception as e:
            return False, 0, f"zstd init failed: {e}"
        try:
            try_extract_from_stream(reader, file_type, outdir_base, preview_only=True)
        except Exception as e:
            return False, 0, f"preview failed: {e}"

        bio2 = io.BytesIO(remaining_bytes)
        try:
            reader2 = dctx.stream_reader(bio2)
        except Exception as e:
            return False, 0, f"second zstd init failed: {e}"
        try:
            success, files = try_extract_from_stream(reader2, file_type, outdir_base, preview_only=False)
            if success:
                return True, files, "Extracted (compressed)"
            return False, 0, "Decompression succeeded but nothing extracted"
        except Exception as e:
            return False, 0, f"extraction error (zstd): {e}"
    else:
        try:
            try_extract_from_stream(bio, file_type, outdir_base, preview_only=True)
        except Exception as e:
            return False, 0, f"preview failed: {e}"

        bio2 = io.BytesIO(remaining_bytes)
        try:
            success, files = try_extract_from_stream(bio2, file_type, outdir_base, preview_only=False)
            if success:
                return True, files, "Extracted (raw)"
            return False, 0, "Preview succeeded but extraction failed"
        except Exception as e:
            return False, 0, f"extraction error (raw): {e}"


def find_all_candidates(path):

    filesize = os.path.getsize(path)
    file_type = detect_file_type(path)
    scan_size = min(filesize, MAX_BYTES_TO_SCAN_FROM_END)

    with open(path, "rb") as f:
        if scan_size < filesize:
            f.seek(filesize - scan_size)
        data = f.read(scan_size)

    candidates = []

    if file_type == "PE":
        rc_end = locate_rcdata_end_pe(path)
        if rc_end is not None:
            with open(path, "rb") as f:
                start_probe = max(0, rc_end - 128)
                f.seek(start_probe)
                probe = f.read(256)
            for h in MAGIC_HEADERS:
                idx = probe.find(h)
                if idx != -1:
                    candidates.append((start_probe + idx, h))

    for offset, h in _scan_for_headers(data):
        candidates.append((filesize - scan_size + offset, h))

    candidates = sorted(set(candidates), key=lambda x: x[0])

    if not candidates:
        with open(path, "rb") as f:
            data_full = f.read()
        candidates = list(_scan_for_headers(data_full))
        candidates = sorted(set(candidates), key=lambda x: x[0])

    return candidates