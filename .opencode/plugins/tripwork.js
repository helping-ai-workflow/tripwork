/**
 * tripwork plugin for OpenCode.ai
 *
 * Injects the tripwork bootstrap context via message transform and
 * auto-registers the skills directory via the config hook (no symlinks).
 */

import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const extractAndStripFrontmatter = (content) => {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { content };
  return { content: match[2] };
};

let _bootstrapCache = undefined; // undefined = not loaded, null = file missing

export const TripworkPlugin = async () => {
  const tripworkSkillsDir = path.resolve(__dirname, '../../skills');

  const getBootstrapContent = () => {
    if (_bootstrapCache !== undefined) return _bootstrapCache;
    const skillPath = path.join(tripworkSkillsDir, 'using-tripwork', 'SKILL.md');
    if (!fs.existsSync(skillPath)) {
      _bootstrapCache = null;
      return null;
    }
    const { content } = extractAndStripFrontmatter(fs.readFileSync(skillPath, 'utf8'));
    const toolMapping = `**Tool Mapping for OpenCode:**
When tripwork skills request actions, substitute OpenCode equivalents:
- Create or update todos -> \`todowrite\`
- Dispatch a subagent -> \`task\` with \`subagent_type: "general"\`
- Invoke a skill -> OpenCode's native \`skill\` tool (always enter tripwork:using-tripwork first)
- Read files -> \`read\`
- Create, edit, or delete files -> \`apply_patch\`
- Run shell commands -> \`bash\`
- Search files -> \`grep\`, \`glob\`
- Consumer-harness \`WebSearch\` -> OpenCode's web-search tool; if none exists, HALT the stage and tell the user (Source-Verified-First: "No search, no fact") — never substitute model memory.`;

    _bootstrapCache = `<EXTREMELY_IMPORTANT>
You have tripwork.

**IMPORTANT: The using-tripwork skill content is included below. It is ALREADY LOADED - you are currently following it. Do NOT use the skill tool to load "using-tripwork" again.**

${content}

${toolMapping}
</EXTREMELY_IMPORTANT>`;
    return _bootstrapCache;
  };

  return {
    config: async (config) => {
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      if (!config.skills.paths.includes(tripworkSkillsDir)) {
        config.skills.paths.push(tripworkSkillsDir);
      }
    },
    'experimental.chat.messages.transform': async (_input, output) => {
      const bootstrap = getBootstrapContent();
      if (!bootstrap || !output.messages.length) return;
      const firstUser = output.messages.find(m => m.info.role === 'user');
      if (!firstUser || !firstUser.parts.length) return;
      if (firstUser.parts.some(p => p.type === 'text' && p.text.includes('EXTREMELY_IMPORTANT'))) return;
      const ref = firstUser.parts[0];
      firstUser.parts.unshift({ ...ref, type: 'text', text: bootstrap });
    }
  };
};
