# git-rewrite

A small Python command-line tool for rewriting messages on the checked-out branch of a local Git clone, reviewing the result, and optionally pushing it to GitHub or another Git remote.

Requires Python 3.9+ and Git. No packages or installation needed. Your normal Git authentication is used.

## Quick start

Download or clone this project, then open Terminal in its directory:

```bash
cd git-rewrite
python3 -m git_rewrite --help
```

Run directly without installing, or install the command into a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
git-rewrite --help
```

On Windows, activate with `.venv\Scripts\activate` and use `python` where the examples say `python3`.
The examples below use `python3 -m git_rewrite`; after installation, you can use `git-rewrite` instead.

Replace `/path/to/repo` below with your local clone. Start with a preview:

```bash
python3 -m git_rewrite /path/to/repo bulk --remove-line 'Co-authored-by: Claude'
```

Use the exact text found in your messages. For example, if your suffix is `Co-author by Claude`, use that instead. Matching is literal and case-sensitive. `--remove-line` removes the entire matching line, including any other text on it.

Once the preview looks right, repeat with `--apply`:

```bash
python3 -m git_rewrite /path/to/repo bulk --remove-line 'Co-authored-by: Claude' --apply
```

The program:

1. Shows message diffs and how many commit IDs will change.
2. Checks that the remote branch matches your local branch.
3. Asks you to type `APPLY`.
4. Creates a backup branch and applies the rewrite locally.
5. Validates every rewritten commit and checks the final file tree and commit count.
6. Asks you to type `PUSH main` (using your actual branch name).
7. Pushes with an explicit force-with-lease and verifies the remote tip.

Press Enter at either confirmation to decline. Preview mode never moves branches, writes commit objects, or contacts the remote. Applying requires a clean working directory, including no untracked files.

## Modes and edits

Replace literal text throughout every reachable commit message:

```bash
python3 -m git_rewrite /path/to/repo bulk --replace 'Co-author by Claude' 'Your custom text' --apply
```

Replace one entire message:

```bash
python3 -m git_rewrite /path/to/repo single --commit abc1234 --message 'Fix login validation' --apply
```

Remove a line from one commit:

```bash
python3 -m git_rewrite /path/to/repo single --commit HEAD --remove-line 'Co-authored-by: Claude' --apply
```

Give all reachable commits the same message (review carefully):

```bash
python3 -m git_rewrite /path/to/repo bulk --message 'Updated commit message' --apply
```

Add `--local-only` to apply without contacting a remote or offering a push. Use `--remote upstream` to select another configured remote. Omit `--apply` from any example to preview only. Multiline messages can be passed as a quoted multiline shell argument.

## Scope and guarantees

- Bulk mode visits every commit reachable from the current branch, including merged history.
- Single mode edits only the selected message; descendants are recreated with updated parent IDs.
- File trees, parent order, merge structure, author/committer identities and timestamps are preserved. No extra commit is appended.
- Only the current branch moves. Other branches and tags keep their original history.
- Changing a message changes its commit ID and descendant IDs. Commit signatures and merge-tag signature headers on recreated commits are removed and reported in the preview.
- Whole-message input is UTF-8. Literal replacements use UTF-8 bytes; untouched message bytes are preserved.
- Shallow clones, detached HEAD, replace references, legacy grafts, and in-progress Git operations are rejected.
- An explicit remote lease prevents overwriting a remote tip that changed since review. GitHub branch protection or authentication can still reject a push; the local rewrite and backup remain available.
- Do not run another tool that modifies this clone while editing. Coordinate rewritten shared history with collaborators.

## Recovery or pushing later

The program prints the backup branch, original tip and new tip. Keep these until you are satisfied. If you decline pushing, your local rewrite remains applied.

To restore the original history locally, ensure the working directory is clean and you are still on the rewritten branch, then replace `BACKUP_BRANCH` below with the printed name:

```bash
git -C /path/to/repo reset --keep BACKUP_BRANCH
```

This moves the local branch only. It does not undo a push already made.

To push an already-reviewed rewrite later, use the original tip from the output as the expected remote value, and the printed new tip as the source. Replace the three uppercase placeholders:

```bash
git -C /path/to/repo push --force-with-lease=refs/heads/BRANCH:ORIGINAL_TIP origin NEW_TIP:refs/heads/BRANCH
```

If the lease fails, inspect the remote changes before proceeding. Do not replace it with an unconditional force push.

## Tests

```bash
python3 -m unittest discover -v
```

Tests create disposable local repositories and a local bare remote. They check single and bulk editing, merge and metadata preservation, preview/cancellation, dirty-clone rejection, backups, successful pushing and remote-change rejection. They do not access GitHub or your repositories.

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
The included GitHub Actions workflow runs the tests for pushes and pull requests.

## Development

The project uses Python's standard library at runtime. Tests use `unittest` and disposable local Git repositories.

```bash
python3 -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [CHANGELOG.md](CHANGELOG.md) for release notes.

## License

MIT. See [LICENSE](LICENSE).
