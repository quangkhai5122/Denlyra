"""Fail CI if mandatory safety labels, AI Agent files or catalog accidentally disappear."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md", "AGENTS.md", "docs/PROJECT_STATE.md",
    "docs/product/PRD.md", "docs/product/FUNCTION_CATALOG.md",
    "docs/clinical/REGULATORY_MATRIX.md", "docs/clinical/EMR_AND_FORMS.md",
    "docs/architecture/DOMAIN_MODEL.md", "docs/architecture/DATABASE.md",
    "docs/security/THREAT_MODEL.md", "docs/operations/DEPLOYMENT.md",
    "docs/engineering/ROADMAP.md", "docs/engineering/TEST_STRATEGY.md",
    "docs/tasks/T001_HARDEN_IDENTITY.md", "backend/src/denlyra/api.py",
    "backend/tests/test_api_basics.py", "apps/demo-web/index.html",
    "docs/engineering/AGENT_WORKFLOW.md", "docs/tasks/T000_REPOSITORY_ONBOARDING.md",
    "scripts/smoke_baseline.py",
]
for file in REQUIRED:
    assert (ROOT / file).is_file(), f"Missing {file}"

code = (ROOT / "backend/src/denlyra/api.py").read_text(encoding="utf-8")
assert '"clinical_e_signature": False' in code
assert '"emr_certified": False' in code
assert '"use_real_patients": False' in code
assert '"production_auth": False' in code
assert '"ai_diagnosis": False' in code

catalog = (ROOT / "docs/product/FUNCTION_CATALOG.md").read_text(encoding="utf-8")
ids = re.findall(r"\| `(\w{2,4}-\d{3})` \|", catalog)
assert len(ids) >= 200 and len(set(ids)) == len(ids), f"Catalog invalid: {len(ids)}"

for p in ROOT.rglob("*.md"):
    if any(part in {"node_modules", "archive", ".venv", ".next", ".git", "local_data"} for part in p.parts):
        continue
    for link in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
        if link.startswith(("https://", "http://", "mailto:", "#")):
            continue
        link = link.split("#")[0]
        if not link:
            continue
        target = p.parent / link
        assert target.exists(), f"Broken link {link} in {p.relative_to(ROOT)}"

print(f"Artifact guard PASS: {len(ids)} catalog IDs, {len(REQUIRED)} mandatory files, safety flags, links")
