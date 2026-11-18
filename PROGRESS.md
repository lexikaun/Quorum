# Quorum development checkpoint

Submission deadline confirmed by the team: 21 November 2026.

## Scope
- Tavily 01. Check each public claim in a supplied answer against version-specific evidence. Preserve the source, quotation, correction and uncertainty. Offer an offline evidence replay.
- Bifrost 02. Compare complete research agents on identical tasks across repeated runs and evidence outages. Show per-run traces, correctness, steps, tools, latency, tokens and cost where observable.

## Starting point
Upstream commit `ee00633` implements Quorum's offline claim memory, citations, sync and owner resolution. The two challenge modules were absent. A single lab will serve both challenges either independently or inside the device UI. Team answers may enter offline replay locally. Live provider calls require explicit input and locally configured credentials.

## In progress
Verifier tested against 9 cases covering version changes, source dates, compound claims, live adapter failures and source provenance. The live transport tests use fixtures. Tests made zero paid calls. Benchmark, UI and integration verification are in progress.

## Git
Original origin retained. Private submission remote is `lexikaun/Quorum`. Use `git log -1 --oneline` and `git ls-remote submission refs/heads/main` to compare the checkpoint.
