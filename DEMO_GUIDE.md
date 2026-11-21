# Quorum demo guide

## Start here

From the repository root, run `python -m lab.server` and open [Quorum Lab](http://127.0.0.1:8765/). This uses Python 3.10+ and the standard library. Local replay, the two built-in benchmark agents, and the recorded Bifrost results work without credentials. Stop the server with Ctrl+C.

## Short presentation

For Quorum, show the Vite 7 receipts in **Freshness verifier**. Open the Node.js 18 sources and switch to Vite 6. Say **Official docs** for the direct-source Vite check and **Tavily search** only if you run the authenticated Tavily mode. For the separate benchmark demo, open **Agent benchmark** on the standalone server and use the recorded Bifrost run to show the gateway trace and token totals.

## Tavily 01. Verify a time-sensitive claim

1. Open **Freshness verifier** and select **Use example** if the answer field is empty.
2. Select **Vite 7** and **Local replay**, then click **Verify answer**. Node.js 18 is superseded, Node.js 22.12 is supported, Node.js 16 is contradicted, and the build-time claim is unknown.
3. Open the Node.js 18 receipt. It includes the older release evidence and newer rule. Switch to **Vite 6** and verify again to see that Node.js 18 still applies to the older release.
4. Select **Official docs** to replay the same claim check with fresh upstream Vite pages and manifests. The verification trace shows fetched sources. This mode uses upstream HTTP directly.
5. With credentials configured, select **Tavily search** to find and extract official Vite sources. The standalone lab also offers **Public web**, which sends queries from up to four public statements to Tavily. It shows passages for manual review and leaves the verdict unverified. A page date alone cannot establish what that page said in a historical edition.

## Bifrost 02. Compare research agents

Open the [standalone benchmark](http://127.0.0.1:8765/#benchmark) after starting `python -m lab.server` from the repository root.

1. Open **Agent benchmark**, set **Repeats per case** to 1, and click **Run benchmark**. The two built-in agents produce 24 fresh runs across 12 cases.
2. Inspect the same case for both agents, such as **v7-node18**. Look at the retrieved source order, target release, verdict, expected result, and trace. Inspect an evidence-outage run to see when the agent abstains.
3. Click **View recorded Bifrost run** to inspect the saved 72-trial result. This includes 24 actual requests through Bifrost to Qwen running on the local CPU. Gateway request IDs and reported token counts appear in its traces. Provider cost was unreported. Use **Download JSON** to export the current result.
4. To rerun through Bifrost on Windows x64, stop the standard lab and use `python scripts/local_bifrost.py`. The initial setup downloads the pinned gateway, llama.cpp and approximately 1 GB of model weights. After startup, choose 1 repeat and run the benchmark. Expect a few minutes for model inference. The recorded result opens immediately for a timed presentation.

For the Release Bench dashboard, start the same stack with `python scripts/local_bifrost.py --port 8770` and open [Release Bench](http://127.0.0.1:8770/benchmark/). Choose an evidence condition for a live head-to-head. Both workflows use the same Qwen model, prompt, Node.js manifest check, and 96-token output cap. One uses the first search result and the other finds the guide for the requested release. **See how they answered** shows each guide, manifest check, and gateway request ID. **Run benchmark** includes the baselines, the Bifrost pair, and any configured HTTP agent. The **Results** view breaks out wrong answers with the old guide first and guesses when no guides were available. **Load recorded Bifrost run** opens the saved result.

When Node.js is on `PATH`, `scripts/local_bifrost.py` starts `scripts/research_agent.mjs` as its own HTTP service. Run `node scripts/research_agent.mjs 18763` to try the agent on its own, or set `LAB_AGENT_URL` to connect a different agent. The harness sends the task, target release, and guides. The agent can return `citations` alongside its verdict, using URLs from the supplied guides.

## Show freshness inside Quorum

Install the device dependencies using the README, then double-click `start-quorum.bat`. Open [the demo device](http://127.0.0.1:8766/?look=studio) and select **Try freshness examples** in the Ask panel. Each example uses cited claims stored on the demo device and saved Vite documentation.

| Example | What to show |
| --- | --- |
| Node.js upgrade | Node.js 18 is superseded and Node.js 22.12 is supported for Vite 7. Open either claim to see the original Quorum note and the documentation. Select Vite 6 and check again to see Node.js 18 supported. |
| Browser build target | The older default, `modules`, is superseded by `baseline-widely-available` in Vite 7. |
| Before Vite 7 shipped | The June 1, 2025 cutoff leaves the claim unverified. Clear the date and click **Check claims** to include the Vite 7 release announcement. |

To show how the same feature works from an answer, ask **What do we know about Vite?** and click **Check claim freshness** beneath the citations.

The panel covers documented Node.js compatibility and default build targets for Vite 6.0 and 7.0. **Saved docs** runs offline and shows when the snapshot was captured. **Official docs** rechecks the expected passages and tagged package manifests online. It uses fixed public URLs, so the claim text stays on the device. Missing or changed passages produce **Unverified**. Expand a claim to see the original note and the evidence used.

Click **Save checks to this device** to keep the displayed results for the cited claim revisions. Take the same steps from the [phone view](http://127.0.0.1:8766/phone) to demonstrate mobile.

## Provider configuration

Set these in the shell before launching the lab. Use public material only in Public web mode.

| Variable | Purpose |
| --- | --- |
| `TAVILY_API_KEY` | Enables the **Tavily search** evidence source. |
| `LAB_BIFROST_URL` | Full gateway chat endpoint, such as `http://127.0.0.1:18762/v1/chat/completions`. |
| `LAB_BIFROST_MODEL` | Bifrost provider and model, such as `openai/quorum-qwen`. |
| `LAB_BIFROST_KEY` | Gateway credential when required. |
| `LAB_AGENT_URL` | Optional framework-independent benchmark adapter. See the [request protocol](lab/benchmark.py). |

Real Tavily API calls require an account key and can consume provider credits.
