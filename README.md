# git-rewrite

A small Python command-line tool for rewriting messages on the checked-out branch of a local Git clone, reviewing the result, and optionally pushing it to GitHub or another Git remote.

Requires Python 3.9+ and Git 2.29+ on PATH (Git for Windows on Windows). No packages or installation needed. Your normal Git authentication is used.

## Quick start

Download or clone this project, then open a terminal in its directory. No installation is needed to run the module.

### macOS and Linux (bash/zsh)

```bash
cd git-rewrite
python3 -m git_rewrite --help
```

Optional installation into a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/git-rewrite --help
```

### Windows (PowerShell or Command Prompt)

Install Python and Git for Windows, then open a new terminal:

```text
cd git-rewrite
py -3 -m git_rewrite --help
```

Optional installation (no environment activation or PowerShell execution-policy change needed):

```text
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\git-rewrite.exe --help
```

If the `py` launcher is unavailable, use `python` instead of `py -3`.
Windows example with a path containing spaces:

```text
py -3 -m git_rewrite "C:\Users\You\My Projects\repo" bulk --remove-line "Co-authored-by: Claude"
```

The commands below use `python3 -m git_rewrite`; on Windows use `py -3 -m git_rewrite` instead.
After installation, the `git-rewrite` executable provides the same options.
Double-quote paths and text containing spaces. For messages containing shell-special characters or multiple lines, use `--message-file` as described below.

Replace `"/path/to/repo"` below with your local clone. Start with a preview:

```bash
python3 -m git_rewrite "/path/to/repo" bulk --remove-line "Co-authored-by: Claude"
```

Use the exact text found in your messages. For example, if your suffix is `Co-author by Claude`, use that instead. Matching is literal and case-sensitive. `--remove-line` removes the entire matching line, including any other text on it.

Once the preview looks right, repeat with `--apply`:

```bash
python3 -m git_rewrite "/path/to/repo" bulk --remove-line "Co-authored-by: Claude" --apply
```

The program:

1. Shows message diffs and how many commit IDs will change.
2. Checks that the remote branch matches your local branch.
3. Asks you to type `APPLY`.
4. Builds and validates the rewritten commits, including the final file tree and commit count.
5. Creates a backup branch and updates the local branch together in one transaction.
6. Asks you to type `PUSH main` (using your actual branch name).
7. Pushes with an explicit force-with-lease and verifies the remote tip.

Press Enter at either confirmation to decline. Preview mode never moves branches, writes commit objects, or contacts the remote. Applying requires a clean working directory, including no untracked files.

## Modes and edits

Replace literal text throughout every reachable commit message:

```bash
python3 -m git_rewrite "/path/to/repo" bulk --replace "Co-author by Claude" "Your custom text" --apply
```

Replace one entire message:

```bash
python3 -m git_rewrite "/path/to/repo" single --commit abc1234 --message "Fix login validation" --apply
```

Remove a line from one commit:

```bash
python3 -m git_rewrite "/path/to/repo" single --commit HEAD --remove-line "Co-authored-by: Claude" --apply
```

Give all reachable commits the same message (review carefully):

```bash
python3 -m git_rewrite "/path/to/repo" bulk --message "Updated commit message" --apply
```

Add `--local-only` to apply without contacting a remote or offering a push. Use `--remote upstream` to select another configured remote. Omit `--apply` from any example to preview only. For multiline messages, save the complete message in a UTF-8 text file outside the target clone (or an ignored location), then run:

```bash
python3 -m git_rewrite "/path/to/repo" single --commit HEAD --message-file "message.txt" --apply
```

Relative message-file paths are resolved from your terminal's current directory. UTF-8 files with a BOM are accepted; CRLF and LF line endings are normalized to LF. Repository file contents are never converted. Empty messages are rejected.

## Scope and guarantees

- Bulk mode visits every commit reachable from the current branch, including merged history.
- Single mode edits only the selected message; descendants are recreated with updated parent IDs.
- File trees, parent order, merge structure, author/committer identities and timestamps are preserved. No extra commit is appended.
- Only the current branch moves. Other branches and tags keep their original history. Automatic tag following is disabled for pushes.
- Changing a message changes its commit ID and descendant IDs. Commit signatures and merge-tag signature headers on recreated commits are removed and reported in the preview.
- Consoles that cannot display a character show an escaped representation instead of crashing; the message stored in Git is unchanged.
- Whole-message input is UTF-8. Literal replacements use UTF-8 bytes; untouched message bytes are preserved.
- Shallow clones, detached HEAD, replace references, legacy grafts, and in-progress Git operations are rejected.
- An explicit remote lease prevents overwriting a remote tip that changed since review. GitHub branch protection or authentication can still reject a push; the local rewrite and backup remain available.
- Do not run another tool that modifies this clone while editing. Coordinate rewritten shared history with collaborators.

## Recovery or pushing later

The program prints the backup branch, original tip and new tip. Keep these until you are satisfied. If you decline pushing, your local rewrite remains applied.

To restore the original history locally, ensure the working directory is clean and you are still on the rewritten branch, then replace `BACKUP_BRANCH` below with the printed name:

```bash
git -C "/path/to/repo" reset --keep BACKUP_BRANCH
```

This moves the local branch only. It does not undo a push already made.

To push an already-reviewed rewrite later, use the original tip from the output as the expected remote value, and the printed new tip as the source. Replace the three uppercase placeholders:

```bash
git -C "/path/to/repo" push --no-follow-tags --force-with-lease=refs/heads/BRANCH:ORIGINAL_TIP origin NEW_TIP:refs/heads/BRANCH
```

If the lease fails, inspect the remote changes before proceeding. Do not replace it with an unconditional force push.

## Tests

```bash
python3 -m unittest discover -v
```

Tests create disposable local repositories and a local bare remote. They check single and bulk editing, merge and metadata preservation, preview/cancellation, dirty-clone rejection, backups, successful pushing and remote-change rejection. They also cover paths with spaces and Unicode, Windows-style text files, limited console encodings, linked worktrees, and disabled automatic tag pushing. They do not access GitHub or your repositories.

## Share on GitHub

Create an empty GitHub repository named `git-rewrite`, without an initial README or license.
From this project directory, run the following, replacing `YOUR_USERNAME` with your GitHub username:

```bash
git init -b main
git add .
git commit -m "Initial release of git-rewrite"
git remote add origin https://github.com/YOUR_USERNAME/git-rewrite.git
git push -u origin main
```

Share your repository link with your friend. They can clone it and follow Quick start.
The included GitHub Actions workflow tests Windows, Linux, and macOS with Python 3.9, 3.12, and 3.14 on pushes and pull requests. Native Windows/Linux verification requires those CI jobs to pass; local macOS tests alone do not establish that.

## Development

The project uses Python's standard library at runtime. Tests use `unittest` and disposable local Git repositories.

```bash
python3 -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [CHANGELOG.md](CHANGELOG.md) for release notes.

## License

MIT. See [LICENSE](LICENSE).
