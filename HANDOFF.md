# Quorum handoff

Quorum stores team knowledge on the device. The current demo lets a teammate ask a question, see the notes behind the answer, and check whether those notes still apply to a selected Vite release.

## Run the demo

1. Follow the Windows Python 3.12 setup in [README.md](README.md), then double-click `start-quorum.bat`.
2. Open [Quorum](http://127.0.0.1:8766/?look=studio). In **Ask**, select **Try freshness examples**, or ask **What do we know about Vite?** and select **Check claim freshness** below the answer.
3. Use **Saved docs** for an offline rehearsal. The Node.js upgrade example shows why Node.js 18 guidance from Vite 6 was superseded for Vite 7.0. The historical example shows **Unverified** when the selected date predates the evidence. Expand a result to compare the saved note with the documentation. **Save checks to this device** saves the displayed result for the cited claim revision.

The app also supports **Official docs**, which fetches known Vite passages and manifests over the internet. It keeps the claim text local. The rules cover declared Node.js compatibility and default build targets for Vite 6.0 and 7.0. The standalone lab can optionally use Tavily to suggest passages for manual review of public claims.

## Where to work

- [In-app panel](app/web/freshness.js) and [styles](app/web/freshness.css) control the desktop and phone experience.
- [Device API](app/edge/api.py) checks cited claim revisions and saves the exact results shown to the user.
- [Verifier](lab/verifier.py) contains the rules and source checks. [Demo launcher](scripts/memory_lab.py) provides the example notes.
- The [demo guide](DEMO_GUIDE.md) covers the standalone benchmark and its Release Bench dashboard.

## Checks and next step

Run these from the repository root after setup. The optional Ollama tests require a local model.

```powershell
. .\scripts\env.ps1
.\app\.venv\Scripts\python.exe -m unittest discover -s lab -q
.\app\.venv\Scripts\python.exe -m pytest app/tests -ra
```

Rehearse the three offline examples from a fresh checkout, then try **Official docs** if internet access is available. A live Tavily run remains to be checked with an authorized key. Use saved docs if official sources are unavailable during the demo. If Windows reports a Qdrant path error during the two-device demo, follow the short checkout path in [README.md](README.md). On Windows, press Ctrl+C in the launcher window to stop the demo and answer **Y** if prompted.
