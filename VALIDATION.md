# Validation of the first local version

Checked on 30 September 2026 on the user's Windows computer.

## Automated checks

`python -m unittest discover -s tests -v`: **17 tests passed**.

The tests cover nested and sibling branch isolation; immutable root-message editing; merges that omit shared ancestors; cross-workspace merge rejection; archive/restore and last-branch protection; nondestructive checkpoint restore; JSON import and cycle validation; merge provenance during import; Host, Origin and mutation-token checks; successful streamed output and correct provider context; saved prompts and retry after provider failure; context trimming without deleting stored history; cached summaries; and 500-message backend retrieval within a two-second assertion.

`node --check public/app.js` and Python compilation checks passed. No npm or pip installation is required by the application itself.

## Browser checks

- Opened the actual application and inspected its mint and baby pink layout.
- Inspected the 1440-pixel desktop layout with map and chat visible together; fixed panel overflow so the composer remains visible.
- Checked a 390-pixel viewport. Document width did not exceed the viewport. Temporary viewport overrides were reset.
- Created **My first project**, saved a note, forked **Explore the interface**, and edited the root prompt into **A simple first milestone**.
- Verified the original note remains on its original branch while the edited prompt occupies a separate branch.
- Opened comparison and export/checkpoint controls.
- Verified the browser's optional branch-list tool returned the visible workspace's branches. Unsupported browsers simply skip tool registration.

## Real local AI check

Downloaded Ollama 0.35.0 from the official GitHub release and extracted its portable CPU runtime (about 66 MB) into the project runtime folder. Downloaded `qwen3:0.6b` through Ollama's registry. The runtime uses project-local model storage and configuration, with cloud features disabled.

Through the visible app, clicked **Reply to saved prompt** on **A simple first milestone**. The real local model generated a two-sentence response; the application displayed it with the `qwen3:0.6b` label and saved it as the second message in that branch. No paid provider, API key or simulated response was used for this check.

## Limits of this validation

The automated provider tests use simulated streams to exercise failure cases reliably. The separate real-model check demonstrates that the Ollama integration works; it does not establish model accuracy or usefulness. This small model is intended as a lightweight starter. No enterprise load testing, security certification, exhaustive accessibility audit, cloud deployment or multi-user validation was performed. The 500-message timing test measures backend retrieval, not graph rendering speed.

## Resume check

Confirmed the saved app and local Qwen model were still available. Fixed the launcher so it restarts a missing portable AI process even when the application is already running, and waits for local AI readiness before opening a newly started app. Added three isolated launcher tests covering reuse, recovery and startup ordering. All 17 tests pass. Existing workspaces and conversations were preserved.
