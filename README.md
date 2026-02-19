# Zo Skills Library

Reusable workflows, pipelines, and tools for [Zo Computer](https://zo.computer).

## Installation

Install any skill into your Zo workspace:

```bash
# From the Zo skills registry
slug="<skill-slug>"; dest="Skills/$slug"
tarball_url="https://github.com/vrijenattawar/zo-skills/archive/refs/heads/main.tar.gz"
archive_root="zo-skills-main"
mkdir -p "$dest" && curl -L "$tarball_url" | tar -xz -C "Skills" --strip-components=1 "$archive_root/$slug"
```

Or clone the entire library:

```bash
git clone https://github.com/vrijenattawar/zo-skills.git
```

## Skills (36)

| Skill | Description |
|-------|-------------|
| [agentmail-inbox-firewall](./agentmail-inbox-firewall/) | Hardened AgentMail webhook receiver operations for multi-inbox routing, security |
| [booking-metadata-calendar](./booking-metadata-calendar/) | Parse natural-language booking requests into structured metadata, wire metadata  |
| [branded-pdf](./branded-pdf/) | Generate clean, professional PDFs with dual-logo headers, customizable styling,  |
| [build-close](./build-close/) | Post-build synthesis for Pulse builds. Aggregates all deposits, synthesizes |
| [careerspan-decomposer](./careerspan-decomposer/) | Decomposes <YOUR_PRODUCT> Intelligence Briefs into structured YAML using LLM sem |
| [careerspan_hiring_intel](./careerspan_hiring_intel/) | Shared library for <YOUR_PRODUCT> Hiring Intelligence. Contains canonical implem |
| [claude-code-window-primer](./claude-code-window-primer/) | Optimizes Claude Code Pro/Max usage by priming the 5-hour rolling window early m |
| [close](./close/) | Universal close skill. Just say "close" and it auto-routes to the right close sk |
| [drop-close](./drop-close/) | Close Pulse worker (Drop) threads. Writes structured deposit JSON for |
| [fillout-survey-monitor](./fillout-survey-monitor/) | Automated monitoring of Fillout survey changes with intelligent refresh triggeri |
| [frontend](./frontend/) | Generate high-quality landing pages with anti-slop guardrails and multi-platform |
| [frontend-design](./frontend-design/) | Create distinctive, production-grade frontend interfaces with high design qualit |
| [frontend-design-anthropic](./frontend-design-anthropic/) | Create distinctive, production-grade frontend interfaces with high design |
| [ga4-analytics](./ga4-analytics/) | Pull Google Analytics 4 traffic stats for V's personal website (<YOUR_GITHUB>.co |
| [gamma](./gamma/) | Generate presentations, documents, social posts, and websites using Gamma's AI A |
| [meme-factory](./meme-factory/) | Generate memes using the memegen.link API. Use when users request memes, want to |
| [mentor-handler](./mentor-handler/) | Handle escalation requests from <YOUR_INSTANCE> instances and provide thoughtful |
| [prompt-to-skill](./prompt-to-skill/) | Convert complex prompts into reusable skills. Assesses prompts for conversion el |
| [pulse](./pulse/) | Automated build orchestration system. Spawns headless Zo workers (Drops) in para |
| [rapid-context-extractor](./rapid-context-extractor/) | Extract and teach key points from a source using seed context, then force active |
| [remotion](./remotion/) | Create videos programmatically with React using Remotion. Scaffold projects, wri |
| [resume-decoded](./resume-decoded/) | Generates <YOUR_PRODUCT> "Resume:Decoded" candidate briefs as 2-page branded PDF |
| [skills-importer](./skills-importer/) | Import skills from skills.sh and GitHub-hosted agentskills.io repositories into  |
| [sourcestack-monitor](./sourcestack-monitor/) | > |
| [systematic-debugging](./systematic-debugging/) | Use when encountering any bug, test failure, or unexpected behavior, before prop |
| [task-system](./task-system/) | ADHD-optimized task management system for Zo. Handles task registry, |
| [text-commute-info](./text-commute-info/) | Gets your commute time and route options, then texts you the details |
| [text-to-diagram](./text-to-diagram/) | Transform text corpora (articles, docs, ideas, decisions) into Excalidraw-ready  |
| [thread-close](./thread-close/) | Close normal interactive conversation threads. Handles tier detection, |
| [vapi](./vapi/) | Voice AI integration with Vapi. Enables inbound/outbound phone calls with AI voi |
| [warmer-jobs](./warmer-jobs/) | > |
| [zo-create-site](./zo-create-site/) | Create a site hosted on your Zo server. Private by default, publish with a click |
| [zo-linkedin](./zo-linkedin/) | LinkedIn tool for searching profiles, checking messages, and summarizing your fe |
| [zo-substrate](./zo-substrate/) | Generalized Zo-to-Zo skill exchange system. Push and pull skills between any two |
| [zo-twitter](./zo-twitter/) | Let Zo use your X (Twitter) account |
| [zo-twitter-2](./zo-twitter-2/) | Let Zo use your X (Twitter) account |

## Contributing

Skills follow the [Agent Skills](https://agentskills.io/specification) spec.
Each skill has a `SKILL.md` with frontmatter and instructions.

## License

MIT

---

Built for [Zo Computer](https://zo.computer) · Updated 2026-02-19
