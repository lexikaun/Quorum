"""Start the offline Quorum device with three cited Vite memories at localhost:8766."""
from datetime import date, datetime
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path[:0] = [str(ROOT), str(APP)]

import uvicorn
from edge.api import create_app
from edge.config import Config

PORT = 8766
DATA_DIR = APP / "data" / "memory-lab"
MEMORIES = (
    ("vite6-node18", "Node.js 18 is supported.", "node_support", "18", "2024-11-26",
     "Vite 6 release announcement", "https://vite.dev/blog/announcing-vite6#node-js-support",
     "Vite 6 supports Node.js 18, 20, and 22+, similar to Vite 5."),
    ("vite6-build-target", "The default build.target is 'modules'.", "build_target", "modules", "2024-11-26",
     "Vite 6.0.0 build configuration", "https://github.com/vitejs/vite/blob/v6.0.0/packages/vite/src/node/build.ts#L343-L344",
     "buildEnvironmentOptionsDefaults = Object.freeze({ target: 'modules',"),
    ("vite7-node22", "Node.js 22.12 is supported.", "node_support", "22.12", "2025-06-24",
     "Vite 7 release announcement", "https://vite.dev/blog/announcing-vite7#node-js-support",
     "Vite now requires Node.js 20.19+, 22.12+."),
)
EXAMPLES = (
    {"title": "Node.js upgrade",
     "question": "Will the team’s Node.js versions work after we move from Vite 6 to Vite 7?",
     "claim_ids": ["vite6-node18", "vite7-node22"]},
    {"title": "Browser build target",
     "question": "Can we use the browser build default from our Vite 6 notes after the upgrade?",
     "claim_ids": ["vite6-build-target"]},
    {"title": "Before Vite 7 shipped",
     "question": "Could the team verify Vite 7’s Node.js requirements on 1 June 2025?",
     "claim_ids": ["vite7-node22"], "as_of": "2025-06-01"},
)


def create_device(data_dir, port):
    cfg = Config(device="research", display_name="Research · Vite memory", data_dir=data_dir,
                 port=port, today=date.today(), hub_collection="quorum_research_demo")
    app = create_app(cfg)
    app.state.freshness_examples = EXAMPLES
    ctx = app.state.ctx
    ctx.sync.set_online(False)
    # Stable IDs let a restart fill a partially seeded shard and preserve user edits.
    with ctx.memory.batch():
        for claim_id, text, attribute, value, day, title, url, excerpt in MEMORIES:
            if ctx.memory.get(claim_id) is not None:
                continue
            at = day + "T00:00:00Z"  # Release dates have day precision.
            ctx.memory.add_claim({
                "claim_id": claim_id, "text": text, "entity": "Vite", "entity_kind": "project",
                "attribute": attribute, "value": value, "value_label": value,
                "source": {"kind": "note", "ref": url, "author": title, "excerpt": excerpt, "at": at},
                "stated_at": at, "captured_by": cfg.device, "device_id": cfg.device_id,
                "owner": cfg.device, "tier": "device", "status": "active", "conflict_id": None,
                "resolves": None, "version": 1, "modified_by": cfg.device,
                "modified_at": int(datetime.fromisoformat(day + "T00:00:00+00:00").timestamp() * 1000),
            })
    return app


def main():
    # Reserve the one demo endpoint before opening its persistent shard.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", PORT))
        listener.listen()
        app = create_device(DATA_DIR, PORT)
        print(f"Open http://127.0.0.1:{PORT}/ and ask: What do we know about Vite?", flush=True)
        config = uvicorn.Config(app, host="127.0.0.1", port=PORT, timeout_graceful_shutdown=2)
        uvicorn.Server(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
