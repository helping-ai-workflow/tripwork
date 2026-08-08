# tripwork (Gemini context)

You have tripwork. The using-tripwork skill is included below and is already
loaded for this session — follow it; do not load it again.

@./skills/using-tripwork/SKILL.md

## Gemini tool mapping

- Ask the user / clarifying questions / multiple choice -> Gemini's interactive prompt.
- Dispatch a subagent -> `invoke_agent`.
- Read / write / run -> `read_file`, `write_file`, `run_shell_command`.
- Consumer-harness `WebSearch` -> Gemini's grounded web search (source ladder rung 1).
  Consumer-harness `WebFetch` -> whatever URL-fetch capability this harness exposes
  (rungs 2/3: an official/local-authority page, else a search engine's HTML endpoint
  for discovery only — never the fact itself). HALT the stage and tell the user only
  when every rung of the source ladder is unavailable (Source-Verified-First:
  "No unsourced fact") — model recall is never a source.
- Always enter tripwork:using-tripwork first, then let tripwork:orchestrator pick the stage.
