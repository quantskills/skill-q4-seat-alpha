# Portable Loader Prompt

Use this prompt in agents that do not natively discover `SKILL.md` folders, including Claude Code, Hermes, and OpenClaw deployments that receive skills as copied folders.

```text
You have access to a local skill named seat-alpha at:
<SEAT_ALPHA_SKILL_ROOT>

When the user asks to build or audit futures seat factors, compare seat signals with CTA, check publication lag sensitivity, or reproduce the Q4 seat-signal study:
1. Read <SEAT_ALPHA_SKILL_ROOT>/SKILL.md.
2. For data contracts and baseline files, read <SEAT_ALPHA_SKILL_ROOT>/references/data_guide.md.
3. Use the local pandadata-api skill to verify exact method parameters before any real Pandadata call.
4. Set PANDA_DATA_USERNAME and PANDA_DATA_PASSWORD before fetching data, or pass --data-dir.
5. Run scripts/validate.py before trusting any result; report failures verbatim.
6. Preserve factor definitions, broker lists, execution timing, cost assumptions, and data dates.
7. Do not invent data interfaces, fields, factors, or trading advice.
```
