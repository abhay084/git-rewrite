# Changelog

## Unreleased

- Test Windows, Linux, and macOS across three Python versions in GitHub Actions.
- Handle Unicode output on consoles using legacy encodings.
- Add UTF-8 message files, including BOM and CRLF support.
- Clarify PowerShell, Command Prompt, bash, and zsh setup without requiring activation.
- Add portability and push-scope regression tests; isolate tests from user Git configuration.
- Disable automatic tag following during a branch push.
- Report missing Git with an actionable error and protect option parsing for commit references and remote URLs.

## 0.1.0

- Single-commit and bulk commit-message editing.
- Literal replacement, matching-line removal, and full-message replacement.
- Preview diffs and explicit apply/push confirmations.
- Automatic local backup, metadata and graph preservation, and validation.
- Push with an explicit force-with-lease and remote verification.
- Installable command, documentation, automated tests, and GitHub Actions workflow.
