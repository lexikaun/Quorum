# Quorum pause checkpoint

Paused at the team's request on 18 November 2026. The team confirmed a 21 November submission deadline. The submission repository is private at https://github.com/lexikaun/Quorum. Its remote is named submission. The original ImTani remote and Git history are preserved. No public deployment or hackathon submission has been made.

## Implemented and verified

- Tavily 01 checks Vite 6/7 runtime compatibility and build-target guidance per claim. It provides cited excerpts, reasons, corrections, supported/superseded/contradicted/unknown outcomes, version and optional date context. Replay works offline. Direct official-source mode was exercised against live Vite pages and tagged manifests. It marked Node 18 superseded and Node 22.12 supported for Vite 7. The Tavily Search/Extract transport was checked using fixtures. A real Tavily account call has not been verified.
- Bifrost 02 compares research agents on 12 labeled tasks with configurable repetition, controlled evidence failures, traces, export, and optional HTTP and Bifrost adapters. A real Bifrost v2.4.0 gateway served CPU-local Qwen through llama.cpp. The saved report at lab/fixtures/local_bifrost_run.json includes 72 trials. Out of 24 trials per agent the first-result reader passed 14, version-aware verifier 24, and Qwen 13. The gateway reported 10,516 tokens. These scores describe the bundled suite only.
- The browser UI has independent verifier and benchmark views, source inspection, date and version selection, recorded-run viewing, and JSON export. The device answer view can pass cited text to offline verification. The mounted API can save checks for the original claim IDs in local device storage. Original memory status and sync outbox are preserved. The standalone verifier, release switch, benchmark traces, and export were exercised in a browser before the final UI edits.
- The pause checkpoint includes the latest UI edits, portable cache paths, the three-claim scripts/memory_lab.py launcher, and the unfinished general public-web tests. Models, binaries, Python environments, caches, and local device data remain ignored on disk. All development workers and identified demo servers were stopped.

## Verification at pause

- From repository root, python -m unittest lab.test_benchmark lab.test_verifier lab.test_server -q passed all 21 tests.
- Two focused device API tests passed for the lab mount and local review storage. JS syntax and Python compilation checks passed. The earlier full device regression run reported 158 passed and 2 optional Ollama tests skipped, before the final review-storage test was added.
- Full lab discovery currently reports 25 tests and 5 errors, including subtest errors in lab/test_public_web.py. These capture the unfinished Public web feature. The Vite verifier and benchmark suites pass independently.

## Exact next step when authorized to resume

From the repository root, run python -m unittest lab.test_public_web -v. Implement the missing Public web dispatch and arbitrary-claim Tavily/Bifrost pipeline against these loopback fixtures. The UI and server already expose the option, while lab/verifier.py still accepts only Vite 6 and Vite 7. Do not spend money on provider calls.

Then verify the complete mounted browser journey using app/.venv/Scripts/python.exe scripts/memory_lab.py on port 8766. Ask about Vite, import the citations, verify for both releases, save, reload, and check that the correct receipts persist. The new launcher and most recent saved-review UI were not verified together before the pause. Resolve normal imports when launching from the app directory, where lab at repository root may not be on sys.path. Finish README setup and DEMO_GUIDE.md, then rerun lab discovery and the full device suite.

The standalone lab can be started from the repository root with python -m lab.server (port 8765). For Git verification, compare git rev-parse HEAD with git ls-remote submission refs/heads/main. main still tracks upstream origin/main, so its upstream ahead count is expected.
