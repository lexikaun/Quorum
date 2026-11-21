# Quorum progress

Submission deadline confirmed by the team as **21 November 2026**. Follow [HANDOFF.md](HANDOFF.md) to run the demo and resume work. The team repository is [lexikaun/Quorum](https://github.com/lexikaun/Quorum), configured as the `submission` remote.

## Demo status

- **Tavily 01.** The in-app verifier checks documented Node.js compatibility and default build targets for Vite 6.0 and 7.0. Users can pick saved docs or recheck known official sources online and save the displayed results, including unverified claims. The standalone Public web mode offers Tavily passages for manual review without assigning a verdict.
- **Bifrost 02.** The benchmark compares agents across 12 shared cases with repeats, evidence outages, traces and JSON export. The recorded 72-trial result includes 24 actual requests through Bifrost v2.4.0 to local Qwen. Out of 24 trials per agent the first-result reader passed 14, version-aware verifier 24, and Qwen 13. Bifrost reported 10,516 tokens. These scores describe the bundled suite only.
- **Project split.** Quorum checks cited answers in its own freshness panel and saves receipts on the device. The Bifrost benchmark is available through the standalone lab server. A separate benchmark project can reuse Quorum’s visual theme. See [DEMO_GUIDE.md](DEMO_GUIDE.md) for launch commands.

## Verified on 18 November 2026

- Full lab discovery passed all 26 tests. Full device suite passed 159 tests and skipped 2 optional Ollama tests.
- Browser checks covered the mounted question, three citations, verification for both Vite releases, save and reload, a 24-trial fresh benchmark, recorded Bifrost results and JSON download.
- Public web was exercised in a real browser against loopback Tavily and Bifrost fixtures. The suite also verifies that a Tavily outage produces an unknown receipt without calling the judge. Official docs mode fetched live Vite sources and returned superseded for Node 18 and supported for Node 22.12 under Vite 7.

- A fresh 36-trial benchmark through the local gateway completed with 12 Bifrost responses, no transport or parse errors, and 5,258 reported tokens. On this run the first-result reader passed 7 of 12, the version-aware verifier 12 of 12, and Qwen 6 of 12.

## Final rehearsal

- Passed 26 lab tests and 160 device tests. Two optional Ollama tests were skipped.
- The original two-device demo passed all 47 checks from a clean, short-path Windows checkout, including offline capture, synchronization, conflict resolution, and device-only data isolation. Qdrant reported a storage-path error from a deeply nested checkout. The README records the working setup.
- The mounted browser flow verified both release scopes, saved cited claim revisions, and loaded their receipts after a reload. The audit fixed a regression where an older claim revision could be presented as the freshly cited one. The API rejects saves against stale citations.
- Standalone browser checks covered live official Vite sources, Public web against the loopback providers, benchmark JSON export, and both demo views at desktop and phone widths. The browser also completed a fresh 36-trial run through local Bifrost. It received all 12 model responses with 5,258 reported tokens and no transport or parse errors. The benchmark defaults to one repeat and reports that inference can take a few minutes.

## Remaining verification

On 21 November 2026, the merged branch passed 161 device tests and 28 lab tests. Two optional Ollama tests were skipped. Edge completed 24 offline benchmark trials, opened the saved Bifrost run, and loaded the standalone Release Bench dashboard.

Real Tavily API calls require authorized credentials and can consume credits. No paid provider calls, public deployment or hackathon submission were made. For a real Tavily demonstration, follow the provider configuration in the demo guide when authorized to use an account key.
