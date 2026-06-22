# tripwork (Gemini context)

You have tripwork. The using-tripwork skill is included below and is already
loaded for this session — follow it; do not load it again.

@./skills/using-tripwork/SKILL.md

## Gemini tool mapping

- Ask the user / clarifying questions / multiple choice -> Gemini's interactive prompt.
- Dispatch a subagent -> `invoke_agent`.
- Read / write / run -> `read_file`, `write_file`, `run_shell_command`.
- Consumer-harness `WebSearch` -> Gemini's grounded web search. If web search is
  unavailable, HALT the stage and tell the user (Source-Verified-First:
  "No search, no fact") — never substitute model memory.
- Always enter tripwork:using-tripwork first, then let tripwork:orchestrator pick the stage.
