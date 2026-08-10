from pathlib import Path

v3 = Path('.github/scripts/apply_mightyslam_patch_v3.py')
wrapper = v3.read_text(encoding='utf-8')

marker = "exec(compile(source, '<mightyslam-patcher-v3>', 'exec'), {"
if wrapper.count(marker) != 1:
    raise SystemExit(f'v3 exec marker mismatch: {wrapper.count(marker)}')

injection = r'''
# v4: the original patch replacement preserved `def test_tooltips_decode():` but
# omitted the newline before its existing indented body, making only the first
# `import` a one-line suite and the following line an unexpected indent.
needle = "def test_tooltips_decode():'''"
if source.count(needle) != 1:
    raise SystemExit(f'tooltips replacement terminator mismatch: {source.count(needle)}')
source = source.replace(needle, "def test_tooltips_decode():\n'''", 1)

# Remove this third-generation wrapper as well when the functional commit lands.
source = source.replace(
    "old_script.unlink(missing_ok=True);old_v2.unlink(missing_ok=True)",
    "old_script.unlink(missing_ok=True);old_v2.unlink(missing_ok=True);Path('.github/scripts/apply_mightyslam_patch_v3.py').unlink(missing_ok=True)",
    1,
)

# Preserve the third failed staging attempt in the diary. It proved the C++ core,
# corpus classifier and risk refresh, but stopped on the generated Python test syntax.
old_log = "- Commit: `{staging}`\\n  - Corrected classifier priority and synthetic knockback geometry, then re-ran the self-removing verified patch after 32/32 `Smsl` observations, multi-target/knockback evidence and same-actor cooldown-gap analysis."
new_log = "- Commit: `ac3da0ee1ed039a3148ffcbaea88ddf2986e4f73`\\n  - Third staging attempt passed the 32/32 corpus classification gate, C++ build/CTest and registry/risk refresh, but the generated Python regression had a missing newline after an existing test function header. No functional commit was produced.\\n- Commit: `{staging}`\\n  - Corrected only the Python regression insertion newline and re-ran the self-removing verified patch; production Mighty Slam mechanics were unchanged from the already CTest/corpus-validated third attempt."
if source.count(old_log) != 1:
    raise SystemExit(f'changelog staging marker mismatch: {source.count(old_log)}')
source = source.replace(old_log, new_log, 1)
'''

wrapper = wrapper.replace(marker, injection + "\n" + marker, 1)
wrapper = wrapper.replace("'<mightyslam-patcher-v3>'", "'<mightyslam-patcher-v4>'", 1)
exec(compile(wrapper, '<mightyslam-v4-wrapper>', 'exec'), {'__name__': '__main__', 'v3': v3})
