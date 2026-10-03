# Installing tripwork for OpenCode

## Prerequisites

- [OpenCode.ai](https://opencode.ai) installed

## Installation

Add tripwork to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["tripwork@git+https://github.com/helping-ai-workflow/tripwork.git"]
}
```

Restart OpenCode. The plugin installs through OpenCode's plugin manager and
registers all tripwork skills.

Verify by asking: "Run tripwork:using-tripwork."
