# Quorum progress

Submission deadline confirmed by the team as **21 November 2026**. Development is in the private [Quorum repository](https://github.com/lexikaun/Quorum). Push through the `submission` remote. The original ImTani `origin` and Git history are preserved.

## Demo status

- **Tavily 01.** Vite 6/7 replay and direct live checks show supported, contradicted, superseded, and unknown claims with dated evidence. General Public web mode uses Bifrost to extract up to four atomic claims, Tavily Search and Extract for evidence, and Bifrost to adjudicate. Quorum checks quote text against retrieved passages and requires distinct dated sources before marking a claim superseded. The backend excludes sources dated after the requested cutoff and omits undated sources for historical checks. Publication dates alone cannot establish historical page contents.
- **Bifrost 02.** The benchmark compares agents across 12 shared cases with repeats, evidence outages, traces and JSON export. The recorded 72-trial result includes 24 actual requests through Bifrost v2.4.0 to local Qwen. Out of 24 trials per agent the first-result reader passed 14, version-aware verifier 24, and Qwen 13. Bifrost reported 10,516 tokens. These scores describe the bundled suite only.
- **Integration.** The device imports a cited answer into the lab, verifies it in local replay, and saves scope-specific receipts on the device. Device startup from the app directory can now import the lab. See [README.md](README.md) for setup and [DEMO_GUIDE.md](DEMO_GUIDE.md) for the two walkthroughs.

## Verified on 18 November 2026

- Full lab discovery passed all 26 tests. Full device suite passed 159 tests and skipped 2 optional Ollama tests.
- Browser checks covered the mounted question, three citations, verification for both Vite releases, save and reload, a 24-trial fresh benchmark, recorded Bifrost results and JSON download.
- Public web was exercised in a real browser against loopback Tavily and Bifrost fixtures. The suite also verifies that a Tavily outage produces an unknown receipt without calling the judge. Official docs mode fetched live Vite sources and returned superseded for Node 18 and supported for Node 22.12 under Vite 7.

- A fresh 36-trial benchmark through the local gateway completed with 12 Bifrost responses, no transport or parse errors, and 5,258 reported tokens. On this run the first-result reader passed 7 of 12, the version-aware verifier 12 of 12, and Qwen 6 of 12.

## Remaining verification

Real Tavily API calls require authorized credentials and can consume credits. No paid provider calls, public deployment or hackathon submission were made. For a real Tavily demonstration, follow the provider configuration in the demo guide when authorized to use an account key.
