# Quorum demo guide

## Start here

From the repository root, run `python -m lab.server` and open [Quorum Lab](http://127.0.0.1:8765/). This uses Python 3.10+ and the standard library. Local replay, the two built-in benchmark agents, and the recorded Bifrost results work without credentials. Stop the server with Ctrl+C.

## Short presentation

Show the Vite 7 receipts in **Freshness verifier**. Open the Node.js 18 sources and switch to Vite 6. Then open **Agent benchmark**, run 1 repeat with the two local agents, and open the recorded Bifrost run to show the gateway trace and token totals. Use the recorded result during a timed pitch so you can inspect the trace immediately. Say **Official docs** for the direct-source Vite check and **Tavily search** only if you run the authenticated Tavily mode.

## Tavily 01. Verify a time-sensitive claim

1. Open **Freshness verifier** and select **Use example** if the answer field is empty.
2. Select **Vite 7** and **Local replay**, then click **Verify answer**. Node.js 18 is superseded, Node.js 22.12 is supported, Node.js 16 is contradicted, and the build-time claim is unknown.
3. Open the Node.js 18 receipt. It includes the older release evidence and newer rule. Switch to **Vite 6** and verify again to see that Node.js 18 still applies to the older release.
4. Select **Official docs** to replay the same claim check with fresh upstream Vite pages and manifests. The verification trace shows fetched sources. This mode uses upstream HTTP directly.
5. With approved credentials already configured, select **Tavily search** to demonstrate Tavily Search and Extract. Select **Public web** for public claims beyond Vite when a Bifrost model is configured too. The model receives the pasted text and extracted evidence, and Tavily receives claim search queries. The verifier examines up to four claims per request and checks proposed quotes against retrieved passages. A superseded verdict requires dated older and newer evidence. Set **As of date** to restrict eligible source dates. A page date alone cannot establish what that page said in a historical edition.

## Bifrost 02. Compare research agents

1. Open **Agent benchmark**, set **Repeats per case** to 1, and click **Run benchmark**. The two built-in agents produce 24 fresh runs across 12 cases.
2. Inspect the same case for both agents, such as **v7-node18**. Look at the retrieved source order, target release, verdict, expected result, and trace. Inspect an evidence-outage run to see when the agent abstains.
3. Click **View recorded Bifrost run** to inspect the saved 72-trial result. This includes 24 actual requests through Bifrost to Qwen running on the local CPU. Gateway request IDs and reported token counts appear in its traces. Provider cost was unreported. Use **Download JSON** to export the current result.
4. To rerun through Bifrost on Windows x64, stop the standard lab and use `python scripts/local_bifrost.py`. The initial setup downloads the pinned gateway, llama.cpp and approximately 1 GB of model weights. After startup, choose 1 repeat and run the benchmark. Expect a few minutes for model inference. The recorded result opens immediately for a timed presentation.

## Show both inside Quorum memory

Install the device dependencies using the README, then run `app/.venv/Scripts/python.exe scripts/memory_lab.py` from the repository root. Open [the demo device](http://127.0.0.1:8766/) and ask **What do we know about Vite?** Click **Check claim freshness** beneath the cited answer. Verify it for Vite 7, click **Save checks to this device**, then switch to Vite 6 and repeat. Reload and open **Local citations** to see the persisted evidence for the selected release. Imported memory stays in local replay. Open **Agent benchmark** from the same lab to demonstrate the second track.

## Provider configuration

Set these in the shell before launching the lab. Use public material only in Public web mode.

| Variable | Purpose |
| --- | --- |
| `TAVILY_API_KEY` | Enables the **Tavily search** evidence source. |
| `LAB_BIFROST_URL` | Full gateway chat endpoint, such as `http://127.0.0.1:18762/v1/chat/completions`. |
| `LAB_BIFROST_MODEL` | Bifrost provider and model, such as `openai/quorum-qwen`. |
| `LAB_BIFROST_KEY` | Gateway credential when required. |
| `LAB_AGENT_URL` | Optional framework-independent benchmark adapter. See the [request protocol](lab/benchmark.py). |

The Public web workflow was verified with loopback provider responses. Real Tavily API calls require an approved account key. They can consume provider credits.
