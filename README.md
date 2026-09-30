# Branch & Bloom

A personal branching AI conversation workspace with a light green and baby pink interface. Runs on your computer with Python, SQLite and Ollama. No paid API, hosted database, account, or JavaScript build step is required.

## Get the source

```text
git clone https://github.com/muskansgit-hub/branch-and-bloom.git
cd branch-and-bloom
python launch.py
```

This is a private repository; cloning requires access to it. Install Python 3.10+ and Ollama, then download `qwen3:0.6b` using the setup steps below. The repository includes all application source, tests, startup scripts, documentation, and the three original planning documents in `docs/reference/`. Personal conversations, downloaded models, portable binaries, logs, and environment secrets are excluded. On a fresh clone, notes and branching work before a model is connected.

## Open the app

On Windows, double-click **Start Branch and Bloom.cmd**, keep its window open, and visit **http://127.0.0.1:8765**. Python 3.10 or newer is required. Python is already available on the computer used to build this project.

Alternatively, from this folder:

```text
python server.py
```

If the port is in use, an existing app instance may already be running. Open the address above, or run `python server.py --port 8766` and visit that port. Stop a server with Ctrl+C in its terminal.

## Portable runtime on this computer

This local project folder includes a portable CPU build of Ollama under `runtime/`. The Windows launcher starts it automatically when no Ollama service is already running, including when the app is open but its AI process has stopped. When the launcher starts or recovers AI, keep its window open. It waits for AI readiness before opening a newly started app. Models are stored under `data/models`, and Ollama configuration is kept under `runtime/profile`. No system installer, PATH change or startup service is used. Cloud features are disabled for this portable process. These runtime and data folders are excluded from the source ZIP and Git.

## Connect free local AI

1. Open Settings & local AI in the app.
2. Install Ollama from https://ollama.com/download/windows if a portable runtime has not already been prepared with this project.
3. Download a small model with `ollama pull qwen3:0.6b`.
4. Keep Ollama running and choose **Refresh connection** in the app.
5. Choose an installed model and send a message.

The initial model download needs internet and disk space. Subsequent inference is local when using local Ollama models. A 0.6B model is a lightweight starting point, not a substitute for the quality of larger commercial models. Additional local models can be installed through Ollama; the app discovers them and remembers the selection per branch. The app requests an 8,192-token context and up to 1,024 output tokens.

Software and local inference have no subscription or API usage charges. Your existing hardware, electricity, storage and internet still have costs. Free cloud quotas are not needed.

## Everyday use

- **New workspace** creates a clean conversation with a main branch.
- **Branch from here** creates an independent path that inherits only messages up to the selected point.
- **Map / Chat / Split** switches between a visual overview and focused conversation. Scroll the map; use Fit view and zoom controls for larger trees.
- **Save note** saves your own text without calling AI. **Reply to saved prompt** asks the selected local model to respond.
- **Edit as branch** preserves the original prompt and places an edited version on a new branch.
- **Compare or merge branches** shows both histories. Merge appends only the source branch's unique messages as a quoted note; it does not rewrite either history or claim to synthesize it.
- **Branch settings** renames, archives or restores a branch. Use Show archived branches to find archived work. The last active branch cannot be archived.
- **Workspace settings** renames a workspace and sets instructions used across its branches.
- **Export** downloads branch Markdown, branch JSON or a full workspace JSON backup. Only full workspace JSON is accepted by the importer.
- **Save checkpoint** records the current workspace. Restore creates a separate workspace so later work is preserved.

The built-in example is explicitly labeled **Example reply**. It is authored demonstration content, not generated AI output.

## Storage and privacy

Conversation data lives in `data/bloom.sqlite3`. The app saves each prompt before generating a reply, and saves complete AI responses. An interrupted or failed response is not stored as if it were complete; the saved prompt can be retried. Draft text is kept only while the page stays open. Selected workspace, branch and view preferences are stored in browser local storage.

Use full workspace JSON exports as portable backups. To copy the database itself, stop the app first and copy the complete `data` folder, including any SQLite WAL files. Do not publish or commit this folder.

This is a **single-user local application**, without account authentication or application-level encryption at rest. It binds only to `127.0.0.1`, validates Host and Origin, uses a per-process request token for mutations, escapes rendered message content, and makes model requests from the server. Other users or programs with access to your operating-system account or files can still access your data. It is not a multi-tenant or internet-facing service.

## Context limits

Only the active branch's ancestors are sent to the model. Token figures are labeled estimates based on UTF-8 size, not exact model tokenization. Output and system-instruction space are reserved. When history is too long, the app attempts to summarize older messages, caches the summary, and retains recent messages. If the summarization input is itself too large or summarization fails, older context is omitted with a visible notice. Original stored messages are never removed. A single oversized prompt is rejected rather than silently shortened.

## Project structure

```text
server.py           Local HTTP API, SQLite, branching and Ollama adapter
public/app.js       Browser interface and conversation tree
public/style.css    Responsive mint and pink theme
public/index.html   Application entry point
public/favicon.svg  Project icon
launch.py           Starts the app and optional portable local AI
tests/test_app.py   Automated integration tests
REQUIREMENTS.md     Document requirements and zero-budget adaptations
data/               Your local conversations (created at first start)
```

The frontend deliberately uses browser-native JavaScript and SVG instead of a framework, and the server uses Python's standard library. This keeps installation free, small and reproducible. The database retains immutable parent-linked messages and content hashes, allowing a later migration to React/Fastify/PostgreSQL without changing the branching concept.

## Checks

```text
python -m unittest discover -s tests -v
node --check public/app.js
```

The integration suite uses isolated temporary databases and a simulated model stream. It covers sibling/nested context isolation, immutable root editing, merge deduplication, cross-workspace rejection, archive/restore, snapshots, backup validation, cross-site protections, streaming persistence, retry after failure, context trimming and a 500-message API retrieval under two seconds. This performance assertion concerns backend retrieval, not browser rendering or model response latency.

## Development configuration

Optional environment variables:

- `BLOOM_DB`: alternative SQLite database file, useful for tests and development.
- `OLLAMA_URL`: trusted Ollama server address, default `http://127.0.0.1:11434`. Changing it to a remote server sends model prompts to that server.

For a production cloud service, replace the local server with a production application server, add authentication and per-user authorization, deploy behind HTTPS, add quotas and migrations, and review privacy, backup and abuse controls. Those are separate product work, not settings that can safely be enabled by exposing this local port.

## References checked for the zero-budget approach

- Ollama's official API: https://github.com/ollama/ollama/blob/main/docs/api.md
- Qwen3 small local model: https://ollama.com/library/qwen3:0.6b
- Ollama Windows download: https://ollama.com/download/windows
- Google Gemini pricing, an optional future cloud alternative with quota and data-use conditions: https://ai.google.dev/gemini-api/docs/pricing

No cloud service is configured in this version.
