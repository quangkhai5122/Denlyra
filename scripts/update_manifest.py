"""Hash version-controlled source files; exclude runtime data and this manifest itself."""
import argparse
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST_SHA256.txt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify without writing")
    args = parser.parse_args()
    listing = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT,
    )
    paths = sorted(set(listing.decode("utf-8").split("\0")) - {"", MANIFEST.name})
    lines = []
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"Missing source file: {relative}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}\n")
    expected = "".join(lines)
    if args.check:
        if not MANIFEST.exists() or MANIFEST.read_text(encoding="utf-8") != expected:
            raise SystemExit("Manifest stale: run python scripts/update_manifest.py after source edits")
        print(f"Manifest PASS: {len(paths)} source files")
    else:
        MANIFEST.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Manifest updated: {len(paths)} source files")


if __name__ == "__main__":
    main()
