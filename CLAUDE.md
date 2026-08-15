# InvForge — agent instructions

Before any `git push` in this repo, run the `invforge-review` skill
against the commits being pushed and get a PASS verdict. This is a hard
requirement (see `.claude/skills/invforge-review/SKILL.md`), not a
suggestion — do not push on a FAIL verdict without the user explicitly
overriding it.

See `docs/coding-standards.md` for the rules that review enforces.
