# audio-duckd

## Project and principles

audio-duckd is a small Linux user-session daemon that attenuates selected
application playback while Linphone streams exist, then restores channel volumes.
Prefer correctness, recoverability, explicit states and small coherent changes.
Understand the existing behavior before editing. Avoid speculative architecture,
unrelated refactors, unnecessary frameworks and new layers without a concrete need.

## Sources of truth

| Source | Responsibility |
| --- | --- |
| `README.md` | Overview, prerequisites, quick start and documentation index. |
| `docs/behavior.md` | Audio behavior, invariants, failure modes and limitations. |
| `docs/configuration.md` | Configuration semantics, defaults and validation. |
| `docs/development.md` | Architecture, environment and local checks. |
| `docs/operations.md` | Execution, diagnosis, recovery and real integration acceptance. |
| GitHub issues | Requested scope, dependencies and acceptance criteria. |

Read relevant documentation and tests before implementing a change. Keep each
contract authoritative in one place and link to it elsewhere. Update the contract
and affected tests together when behavior changes. Resolve conflicts with newer
user instructions explicitly; do not silently invent product decisions.

Always use English for all source code, identifiers, comments, docstrings, tests,
CLI help, errors, technical diagnostics and log messages. This rule applies to
existing code as well as new changes, with no Spanish exception for CLI text or
logs. Project documentation may remain Spanish.

## Architecture and audio integrity

Preserve the module boundaries described in `docs/development.md`: the entry point
coordinates lifecycle, configuration validates inputs, the backend encapsulates
libpulse, detection identifies activity and targets, and policy owns volume state.
Keep domain decisions independent from the external audio adapter. Compatibility
launchers must delegate rather than implement a second audio policy.

Preserve these invariants unless an explicit requirement changes the contract:

- Write only to configured target playback streams; never write mute or change
  Linphone/Discord volumes. Keep backend write guards as well as target filtering.
- Attenuate proportionally per channel, preserve balance and avoid cumulative
  attenuation. Restore the original saved volumes when activity ends.
- Do not transfer saved state to a new stream when an index is reused. Recheck
  identity and channel count before writing; respect the API's race limitations.
- Validate configuration before connecting to or modifying audio.
- Keep inspection read-only and distinguish enumeration failures from empty lists.
- Report failures and restoration limits honestly; never claim guaranteed recovery
  after SIGKILL or loss of the audio server.

The current Linphone trigger is stream presence, not SIP state or signal level.
Discord signal parameters are a future contract, not implemented detection.
Automated fakes cannot establish real application stream lifecycle behavior.

## Working method and validation

Read the full request or issue, its dependencies and acceptance criteria; inspect
the affected code and tests; make the smallest coherent change; update relevant
contracts and tests; validate and review the diff for scope and accidental complexity.
Preserve pre-existing user changes and do not include them in unrelated commits.

Use pytest as the test runner, with development dependencies declared in
`requirements-dev.txt`. Existing `unittest.TestCase` tests remain supported.
Use `./check.sh` as the complete local validation entry point. Focused tests are
useful during development; the complete check must pass before requesting review.
Never hide, disable or delete unrelated tests to obtain green output. Select tests
for observable behavior and material failure risks, not implementation details.

Local validation must not start the daemon, change user audio, control services,
install dependencies or initiate calls. Keep real integration checks separate and
record results using `docs/operations.md`. Report unavailable environments and
unexecuted acceptance criteria explicitly; continue independent work when possible.

When asked to inspect, explain or plan, do not edit files unless requested.
When asked to advance through issues, refresh the backlog and explicit dependencies
between issues. A closed issue or green tests do not satisfy a real-world gate.
Ask only for decisions that materially affect the product or for unresolved conflicts;
choose routine implementation details using the existing contracts.

## Commits and review

Work on a dedicated `codex/` branch for implementation. Create atomic commits as
coherent authorized changes are completed, without waiting for a separate request. Review
the staged diff and run relevant checks before each commit. Exclude secrets,
session logs, generated artifacts and local environment files.

Write commit messages in English as `Type: Imperative summary`, using `Feat`,
`Fix`, `Refactor`, `Test`, `Docs` or `Chore`. Prefer titles under 72 characters;
never exceed 100. Place `Ref #N` on a separate final line for issue work using real
newlines. A PR that completes all acceptance criteria may use `Closes #N` in its
description; never close partially completed work automatically.

After validation, push the working branch automatically and create or update a
PR targeting `main`, without asking for separate push or PR permission. The user
reviews the PR and owns the merge decision. Never merge, enable auto-merge or push
implementation directly to `main`. Preserve unrelated pre-existing changes; this
workflow does not authorize publishing them. Do not amend or rewrite history unless explicitly requested. Verify the
actual issue state after integration before reporting it closed.

Report the changes, validation results, commits/PR if created, and remaining
limitations. Distinguish implemented behavior from real-world verification.
