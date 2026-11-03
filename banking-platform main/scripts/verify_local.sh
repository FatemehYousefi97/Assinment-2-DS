#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m compileall -q app tests scripts
python3 -m unittest discover -s tests/unit -v
python3 -c 'import json,yaml; json.load(open("config/shards.json")); c=yaml.safe_load(open("docker-compose.yml")); assert len(c["services"])==10; print("JSON and Compose YAML: VALID (10 services)")'
python3 -c 'from pypdf import PdfReader; p=PdfReader("output/pdf/Technical_Report.pdf"); assert len(p.pages) <= 10; print("PDF page count:",len(p.pages))'
echo "Local structural checks PASS. This does not execute Docker/PostgreSQL integration tests."

