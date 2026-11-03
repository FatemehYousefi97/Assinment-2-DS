# Actual local verification, 2026-10-25

This is an observed **local-only** log. It must not be presented as a full-system run.

| Command / capability | Actual outcome |
| --- | --- |
| `python3 -m compileall -q app tests scripts` | PASS; no syntax errors |
| `python3 -m unittest discover -s tests/unit -v` | PASS: 4/4 shard map tests, 0.002 seconds |
| `yaml.safe_load(open('docker-compose.yml'))` | PASS: valid YAML parse, 10 services |
| `pdfinfo output/pdf/Technical_Report.pdf` | PASS: 6 A4 pages |
| `docker info` | BLOCKED: `docker: command not found` |
| `python3 -m pip install ... -r requirements.txt` | BLOCKED: package index unavailable; attempted once in sandbox and once with approved execution |
| PostgreSQL-based integration tests | NOT RUN |
| All seven full-system experiments | NOT RUN |
| Coordinator/participant crash tests | NOT RUN |
| GitHub / Docker Hub publication | NOT RUN; requires owner's account and permissions |

These rows apply **only to the initial code-generation sandbox**. Subsequently, the student executed the real Docker/PostgreSQL experiments on their Apple Silicon Mac; those actual passing results, the discovered restart deadlock, the fixes, and the persistence proof are recorded separately in `MAC_VALIDATION_2026-10-25.md`. Neither the earlier limitations nor the later Mac PASS results have been fabricated. Source publication and both expert bonuses still require the student's later decisions.

