from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[2]
changelog=root/'changelog.md'
with changelog.open('a',encoding='utf-8') as f:
    f.write('''\n\n### Main-front live plumbing CI and report synchronization\n\n- Commit: `a9be0434b940ef13220ed8f5628c4cddd47b07bd`\n  - Added the local pairing/auth daemon integration test to the standard repository CI.\n- Commit: `3850f1ccfc1283546e7c8ed0ec8d38f8dc31e3ec`\n  - Added revision-bound stale-search cancellation integration to standard CI.\n- Commit: `676da42b754ee9d1409cc27e8ad1dfec26d17e6c`\n  - Added the live recommendation revision/hash binding contract to standard CI.\n  - Workflow run `31365724181`: **PASS**.\n  - Verified C++ configure/build/CTest, pairing/auth integration, stale-search cancellation integration, live recommendation binding, the full Python pytest suite, TypeScript typecheck and extension build.\n- Commit: `d920ba47bf4e99832c377fe25467dee50f99235c`\n  - Added `docs/LIVE_VALIDATION.md` with the active authenticated battle smoke gate, expected trace sequence, pass criteria, and evidence-driven runtime-fallback decision rule.\n- Commit: `5af650101bedab884dddfbb9ffeeb48abe8f2283`\n  - Added `docs/MAIN_FRONT_STATUS.md` to preserve the main-lane checkpoint while abilities continue independently on branch `ability`.\n- Commit: `d77e25350464bc0d8d57e4793b11bfc21cb7cf8c`\n  - Synchronized `TEST_REPORT.md` with the three mandatory closed-loop integration gates and current ability metrics.\n- Commit: `6807a34dc4c7046db0ee5881a5383c93429eb43a`\n  - Synchronized `IMPLEMENTATION_REPORT.md` with pairing, revision cancellation, live trace/binding, current ability risk and branch ownership.\n- Commit: `499c9c8e20113aa5748f075e9a12dd6609c258fc`\n  - Synchronized the duplicate implementation checkpoint `HeroesWM_Solver_Implementation_Report_0.3.0.md`.\n''')
subprocess.run(['git','config','user.name','github-actions[bot]'],cwd=root,check=True)
subprocess.run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],cwd=root,check=True)
subprocess.run(['git','add','changelog.md'],cwd=root,check=True)
subprocess.run(['git','commit','-m','docs: record main-front CI and report sync'],cwd=root,check=True)
subprocess.run(['git','push','origin','HEAD:main'],cwd=root,check=True)
