# Contributing

Keep changes focused and include a description of the behavior you changed.

Run `python3 -m unittest discover -s tests -v` before opening a pull request.
Tests must use disposable repositories, never a contributor's real clone or GitHub account.

Preserve preview-only behavior, explicit apply/push confirmations, backup creation,
commit-tree and metadata validation, and the explicit remote lease. Include regression
tests for changes to these guarantees. Never log credentials or add secrets to fixtures.
