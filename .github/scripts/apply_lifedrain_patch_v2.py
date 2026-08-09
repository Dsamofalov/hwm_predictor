from pathlib import Path

source = Path('.github/scripts/apply_lifedrain_patch.py').read_text(encoding='utf-8')
source = source.replace(
    "SCRIPT = Path('.github/scripts/apply_lifedrain_patch.py')",
    "SCRIPT = Path('.github/scripts/apply_lifedrain_patch_v2.py')",
    1,
)
source = source.replace(
    "run('git', 'diff', '--check')",
    "run('git', 'diff', '--check', '--', 'cpp/src/simulator.cpp', 'cpp/tests/test_main.cpp', 'python/hwm_solver/knowledge/build_ability_registry.py')",
    1,
)
source = source.replace(
    "if SCRIPT.exists():\n    SCRIPT.unlink()",
    "if SCRIPT.exists():\n    SCRIPT.unlink()\nPath('.github/scripts/apply_lifedrain_patch.py').unlink(missing_ok=True)",
    1,
)

if "run('git', 'diff', '--check')" in source:
    raise SystemExit('failed to narrow diff check')
if "apply_lifedrain_patch.py').unlink(missing_ok=True)" not in source:
    raise SystemExit('failed to add cleanup for first temporary script')

exec(compile(source, '<life-drain-patcher-v2>', 'exec'), {'__name__': '__main__'})
