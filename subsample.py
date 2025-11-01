
import argparse, csv, os, random, shutil
from pathlib import Path

def read_metadata(meta_path: Path):
    rows = []
    with meta_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # LJSpeech: id|text|normalized_text
            parts = line.split("|", 2)
            if len(parts) < 3:
                # tolerate files missing normalized_text (rare)
                if len(parts) == 2:
                    parts.append(parts[1])
                else:
                    continue
            pid, text, norm = parts[0], parts[1], parts[2]
            rows.append((pid, text, norm))
    return rows

def main():
    ap = argparse.ArgumentParser(description="Subsample LJSpeech by fixed number of WAVs (no duration filtering).")
    ap.add_argument("--src", type=Path, required=True, help="Path to LJSpeech root (contains wavs/ and metadata.csv)")
    ap.add_argument("--dst", type=Path, required=True, help="Output directory (will contain wavs/ and metadata.csv)")
    ap.add_argument("--count", type=int, required=True, help="Number of items to keep (random sample)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    ap.add_argument("--copy", action="store_true", help="Copy files instead of hardlink")
    args = ap.parse_args()

    src_root: Path = args.src
    dst_root: Path = args.dst
    src_meta = src_root / "metadata.csv"
    src_wavs = src_root / "wavs"

    assert src_meta.is_file(), f"metadata.csv not found: {src_meta}"
    assert src_wavs.is_dir(), f"wavs dir not found: {src_wavs}"

    rows = read_metadata(src_meta)
    total = len(rows)
    if total == 0:
        raise SystemExit("metadata.csv is empty or invalid.")

    n = min(args.count, total)
    print(f"Total items: {total}. Selecting: {n} (seed={args.seed})")

    random.seed(args.seed)
    # Stable random sample of indices
    indices = sorted(random.sample(range(total), n))
    selected = [rows[i] for i in indices]

    # Prepare output structure
    dst_wavs = dst_root / "wavs"
    dst_wavs.mkdir(parents=True, exist_ok=True)

    # Write new metadata
    meta_out = dst_root / "metadata.csv"
    with meta_out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="|")
        for pid, text, norm in selected:
            w.writerow([pid, text, norm])

    # Copy/Link wavs
    errors = 0
    for pid, _, _ in selected:
        src = src_wavs / f"{pid}.wav"
        dst = dst_wavs / f"{pid}.wav"
        if not src.exists():
            print(f"[WARN] Missing wav: {src}")
            errors += 1
            continue
        if dst.exists():
            continue
        try:
            if args.copy:
                shutil.copy2(src, dst)
            else:
                os.link(src, dst)  # hardlink (fast, saves space). On some filesystems this may fail.
        except Exception as e:
            # fallback to copy if hardlink fails
            try:
                shutil.copy2(src, dst)
            except Exception as e2:
                print(f"[ERROR] Could not copy/link {src} -> {dst}: {e2}")
                errors += 1

    kept = n - errors
    print(f"Done. Wrote {kept} items to: {dst_root}")
    print("New files:")
    print(f" - {meta_out}")
    print(f" - {dst_wavs}")

if __name__ == "__main__":
    main()
