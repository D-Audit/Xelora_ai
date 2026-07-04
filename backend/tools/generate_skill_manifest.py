"""
tools/generate_skill_manifest.py
Run this every time you add or edit a skill in skills/library/<name>/.
Regenerates skills/library/_manifest.json with a fresh SHA-256 hash of
every skill's SKILL.md and impl.py. skills/loader.py refuses to load
any skill folder that ISN'T listed here, or whose files don't match
their pinned hash - see skills/loader.py's docstring for why.

Usage:
    python tools/generate_skill_manifest.py
"""
import hashlib
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY_DIR = os.path.join(PROJECT_ROOT, "skills", "library")
MANIFEST_PATH = os.path.join(LIBRARY_DIR, "_manifest.json")


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    if not os.path.isdir(LIBRARY_DIR):
        print(f"No such directory: {LIBRARY_DIR}")
        sys.exit(1)

    manifest = {}
    for name in sorted(os.listdir(LIBRARY_DIR)):
        folder = os.path.join(LIBRARY_DIR, name)
        if not os.path.isdir(folder):
            continue
        md_path = os.path.join(folder, "SKILL.md")
        impl_path = os.path.join(folder, "impl.py")
        if not (os.path.isfile(md_path) and os.path.isfile(impl_path)):
            print(f"SKIPPED '{name}': missing SKILL.md or impl.py")
            continue

        category = "general"
        with open(md_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("category:"):
                    category = line.split(":", 1)[1].strip()
                    break

        manifest[name] = {
            "sha256_skill_md": sha256_of(md_path),
            "sha256_impl": sha256_of(impl_path),
            "category": category,
        }
        print(f"  + {name}")

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print(f"\nWrote {len(manifest)} skill(s) to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
