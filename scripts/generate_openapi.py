"""Write or verify the checked-in FastAPI OpenAPI contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "python" / "agents"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from sira_api.main import app  # noqa: E402

OUTPUT = ROOT / "contracts" / "openapi" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != generated:
            sys.stdout.write(
                "OpenAPI drift detected; run: .venv\\Scripts\\python.exe "
                "scripts/generate_openapi.py\n"
            )
            return 1
        sys.stdout.write("OpenAPI contract is current.\n")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generated, encoding="utf-8", newline="\n")
    sys.stdout.write(f"Wrote {OUTPUT.relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
