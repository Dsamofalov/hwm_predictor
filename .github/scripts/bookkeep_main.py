from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").replace("\r\n", "\n")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def replace_required(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count < 1:
        raise RuntimeError(f"missing required replacement {label}: {old!r}")
    return text.replace(old, new)


def run(*args: str) -> str:
    proc = subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if proc.returncode:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(args)}\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


run("git", "config", "user.name", "github-actions[bot]")
run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

for path in ("SPEC.md", "HeroesWM_Solver_TZ_Status_0.3.0.md"):
    text = read(path)
    text = replace_required(text, "5373/5481 = 98.03%", "5384/5481 = 98.23%", f"{path} compact legal metric")
    text = text.replace("**98.03%**", "**98.23%**")
    text = text.replace("с **98.03%** к acceptance **>=99.9%**", "с **98.23%** к acceptance **>=99.9%**")
    text = text.replace(
        "После перевода repository в public CI должен использовать GitHub-hosted Windows runners; self-hosted runners больше не являются частью permanent contract.",
        "Permanent CI теперь использует GitHub-hosted `windows-2022`; self-hosted runners удалены и больше не являются частью permanent contract.",
    )
    text = text.replace(
        "После перевода репозитория в public permanent CI должен выполняться на GitHub-hosted Windows runners; self-hosted runners удалены.",
        "После перевода репозитория в public permanent CI выполняется на GitHub-hosted `windows-2022`; self-hosted runners удалены.",
    )
    write(path, text)

if read("SPEC.md") != read("HeroesWM_Solver_TZ_Status_0.3.0.md"):
    raise RuntimeError("SPEC/checkpoint duplicate diverged after bookkeeping patch")

report = read("TEST_REPORT.md")
report = replace_required(report, "5,373", "5,384", "TEST_REPORT representable count")
report = report.replace("98.03%", "98.23%")
report = report.replace(
    "Supported product/CI platform:                  Windows 10/11 x64",
    "Supported product/CI platform:                  Windows 10/11 x64 via GitHub-hosted windows-2022",
)
write("TEST_REPORT.md", report)

changelog = read("changelog.md")
marker = "### Hosted Windows CI migration and legal-geometry correction"
if marker in changelog:
    raise RuntimeError("bookkeeping marker already present")
block = r'''
### Hosted Windows CI migration and legal-geometry correction

- Commit: `2124d80473015761beeb3160749c366b4b3b92e9`.
  - Migrated permanent `HWM / Core` and `HWM / Full` from removed self-hosted labels to GitHub-hosted `windows-2022`, preserving the VS2022/MSVC contract and read-only repository contents permission.
  - Updated `python/tests/test_workflow_contract.py` to reject `self-hosted`/`hwm-windows` and require exactly two hosted Windows 2022 suites.
  - Hosted Actions run `31438342758`: **Core PASS + Full PASS**.
- Commit: `ffb2a301ba57c040a07de55bdc91c8354e50e4c5`.
  - Fixed the main-owned legal-coverage evaluator to use the canonical raw battlefield `x=1..12, y=1..20` instead of shrinking the lower Y bound to currently occupied cells.
  - Mirrored replay's conservative overloaded 2x2 raw-cell canonicalization only when direct big-stack placement is physically impossible.
  - Added focused geometry regressions and refreshed `data/reports/decoder-geometry-audit.json`.
  - Held-out basic-action representability improved **5373/5481 = 98.03% -> 5384/5481 = 98.23%** with failure count **108 -> 97** and no newly introduced failure identities in the corpus A/B audit.
  - Python replay final-overlap debt remains **21 battles / 23 pairs** on the committed evaluator-only tree; the production C++ structural-invalid gate remains open and is being audited separately without weakening invariants.
  - Hosted Actions run `31439876436`: **Core PASS + Full PASS**.
'''
changelog = changelog.rstrip() + "\n\n" + block.strip() + "\n"
write("changelog.md", changelog)

for path in (".github/scripts/bookkeep_main.py", ".github/workflows/bookkeep_main.yml"):
    p = ROOT / path
    if p.exists():
        p.unlink()

run("git", "add", "--", "SPEC.md", "HeroesWM_Solver_TZ_Status_0.3.0.md", "TEST_REPORT.md", "changelog.md", ".github/scripts/bookkeep_main.py", ".github/workflows/bookkeep_main.yml")
run("git", "diff", "--cached", "--check")
run("git", "commit", "-m", "docs: sync hosted CI and legal geometry metrics [skip ci]")
if run("git", "status", "--porcelain"):
    raise RuntimeError("dirty tree after bookkeeping commit")
run("git", "push", "origin", "HEAD:main")
print(run("git", "rev-parse", "HEAD"))
