# Contributing

Keep changes focused and include a description of the behavior you changed.

Run `python3 -m unittest discover -s tests -v` before opening a pull request.
Tests must use disposable repositories, never a contributor's real clone or GitHub account.

Preserve preview-only behavior, explicit apply/push confirmations, backup creation,
commit-tree and metadata validation, and the explicit remote lease. Include regression
tests for changes to these guarantees. Never log credentials or add secrets to fixtures.

CI runs all tests on Windows, Linux, and macOS with Python 3.9, 3.12, and 3.14.
Keep subprocess arguments as a list and commit objects as bytes; avoid shell commands
and implicit text encodings in implementation code. Use UTF-8 explicitly for fixture
files and include paths with spaces in integration tests. Do not claim native platform
verification until the corresponding CI jobs have passed.
