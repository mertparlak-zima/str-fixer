<!-- zima:workspace-context v2 -->

# Workspace context (maintained by zima — do not edit per-repo)

This repository is a member of the **zima** workspace. All links below are relative
to this repository's root at `zima/projects/str-fixer/`.
Workspace router: `../../AGENTS.md`.
Card: `../../repos/str-fixer.md`.

Rules that apply regardless of repo-local rules (never-loosened set):

- **Chain of command** (2026-10-16): subagents never contact the user directly — Telegram
  included. Report to the leader; the leader asks the user.
- **Telegram is outbound-only**: only the leader sends notifications using
  `../../scripts/telegram-notify.mjs`. No listener, MCP server or replies.
  Schema: `../../docs/telegram/NOTIFICATIONS.md`.
- **Temp files**: `.agent-tmp/<task>/` inside this repo; never AppData; never committed;
  cleaned task-scoped. PARKED decision files live in zima's `.local-state/parked/` (durable).
- **Issues**: this repo's issues follow `../../docs/issues.md` — legacy (marker-less) issues
  are READ-ONLY; commit messages use `Refs #N` (never auto-close keywords); `Closes #N`
  lives in the PR body only; gh writes are leader-only.
- **Runners**: labels are routing; never stop another repo's runner or quit Docker
  Desktop; see `../../docs/runners.md`.
- **Workspace credentials**: Telegram bot token/chat ID come from ignored root
  `../../.env`; never print or commit them. Other credentials keep their existing storage.
  Existing product
  signing material and explicitly approved private product artifacts follow repo-local
  protection rules; this block never authorizes reading, publishing or committing them.
- **Git boundaries**: this repo is an independent git root; never treat the workspace as
  one repo.
- **Review**: workspace risk-based T0–T3 minimums apply; keep stricter local acceptance
  gates. Mandatory policy conflicts are patched at their actual source before cutover.


## Workspace task sizing and review floor

Read the policy at workspace-root `.agents/skills/zima-leader/SKILL.md` before
delegation or tier selection; record tier/rationale and rules read before implementation.
T0 has no behavior/policy change; T1 is a tested single-file small low-risk change;
T2 requires one independent reviewer; T3 requires two independent reviewers with
different lenses for data/evidence/contracts/CI/device/security/PII risk, large changes
or cross-repo scope. Merge intent alone is not T3. Preserve stricter project acceptance
gates. Reviewers are shell-less; worker/leader runs tests and supplies evidence.
Use one write worker per repository; read-only exploration may run in parallel.
Workspace Telegram is leader-only and one-way; main-session decisions/park files replace
Telegram questions. Product bot, device, CI, evidence and privacy contracts remain intact.

# Repository entry rules

Read [README](README.md), then the matching skill fully before work.
Media/subtitles are irreplaceable local state and never committed. Preserve
encoding/resync/OCR verification and actual-player test rules.

- All CI runs MUST execute on the local self-hosted Docker runner `str-fixer-docker-1` with labels `[self-hosted, linux, x64, docker, str-fixer]` (`infra/runner/compose.yml`, started via `scripts/start-ci-runner.ps1`). GitHub-hosted runners (`ubuntu-latest`, etc.) are forbidden.
- [srt-fixing](.claude/skills/srt-fixing/SKILL.md)
- [srt-resync](.claude/skills/srt-resync/SKILL.md)
- [pgs-extract](.claude/skills/pgs-extract/SKILL.md)
