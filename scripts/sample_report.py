"""Gera o resumo pós-partida de exemplo a partir de tests/fixtures/sample_match.json.

Serve para ajustar o visual da página sem precisar jogar:

    python scripts/sample_report.py

A página sai em dist/resumo-exemplo.html.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from post_match_report import render_html  # noqa: E402


def main():
    match = json.loads((ROOT / "tests" / "fixtures" / "sample_match.json").read_text(encoding="utf-8"))
    output = ROOT / "dist" / "resumo-exemplo.html"
    output.parent.mkdir(exist_ok=True)
    output.write_text(render_html(match), encoding="utf-8")
    print(f"Resumo de exemplo: {output}")


if __name__ == "__main__":
    main()
