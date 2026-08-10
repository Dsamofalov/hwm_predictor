from pathlib import Path

old = Path('.github/scripts/apply_local_pairing_patch.py')
source = old.read_text(encoding='utf-8')
source = source.replace(
    'SCRIPT = ROOT / ".github/scripts/apply_local_pairing_patch.py"',
    'SCRIPT = ROOT / ".github/scripts/apply_local_pairing_patch_v2.py"',
    1,
)

# Existing GitHub Actions token may push normal source changes but cannot modify
# an existing workflow. The permanent CI step is added after the functional push
# through the GitHub connector instead.
start = source.index('# Keep the integration check in normal CI, not only in this one-shot runner.')
end = source.index('# Specification bookkeeping:', start)
source = source[:start] + source[end:]
source = source.replace(
    'run("npm", "install", "--no-audit", "--no-fund", cwd=ROOT / "extension")',
    'run("npm", "install", "--no-audit", "--no-fund", "--no-package-lock", cwd=ROOT / "extension")',
    1,
)
source = source.replace(
    'WORKFLOW.unlink(missing_ok=True)\nSCRIPT.unlink(missing_ok=True)',
    'WORKFLOW.unlink(missing_ok=True)\nSCRIPT.unlink(missing_ok=True)\nold.unlink(missing_ok=True)',
    1,
)
exec(compile(source, '<local-pairing-patcher-v2>', 'exec'), {
    '__name__': '__main__',
    '__file__': str(old),
    'old': old,
})
