from pathlib import Path

old=Path('.github/scripts/sync_main_spec_checkpoint.py')
source=old.read_text(encoding='utf-8')
source=source.replace("'**Дата:** 10.08.2026  '","'**Дата:** 10.08.2026'",1)
source=source.replace(
    "'**Последнее обновление реализации:** 10.08.2026 — основной front: persistent pairing/bearer auth, revision-bound cooperative stale-search cancellation, live revision/hash trace/binding, authenticated local WebSocket streaming и Linux + Windows/MSVC CI gates реализованы; ability-front ведётся отдельно в ветке `ability`.  '",
    "'**Последнее обновление реализации:** 10.08.2026 — основной front: persistent pairing/bearer auth, revision-bound cooperative stale-search cancellation, live revision/hash trace/binding, authenticated local WebSocket streaming и Linux + Windows/MSVC CI gates реализованы; ability-front ведётся отдельно в ветке `ability`.'",
    1,
)
source=source.replace(
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True)",
    "WORKFLOW.unlink(missing_ok=True);SCRIPT.unlink(missing_ok=True);Path('.github/scripts/sync_main_spec_checkpoint_v2.py').unlink(missing_ok=True)",
    1,
)
exec(compile(source,'<sync-main-spec-v2>','exec'),{
    '__name__':'__main__',
    '__file__':str(old),
    'Path':Path,
})
