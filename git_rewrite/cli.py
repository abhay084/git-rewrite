#!/usr/bin/env python3
"""Review and rewrite commit messages on the checked-out branch. Python 3.9+."""
import argparse
import difflib
import pathlib
import subprocess
import sys
import uuid


class Error(Exception):
    pass


def git(repo, *args, data=None):
    p = subprocess.run(['git', '-C', str(repo), *args], input=data,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise Error(p.stderr.decode('utf-8', 'replace').strip() or 'Git command failed')
    return p.stdout


def text(repo, *args):
    return git(repo, *args).decode('utf-8', 'strict').strip()


def split_commit(raw):
    head, msg = raw.split(b'\n\n', 1)
    fields = []
    for line in head.split(b'\n'):
        if line.startswith(b' '):
            fields[-1] += b'\n' + line
        else:
            fields.append(line)
    return fields, msg


def transform(message, args):
    # Preserve untouched bytes, including non-UTF-8 messages.
    if args.message is not None:
        return args.message.encode('utf-8').rstrip(b'\n') + b'\n'
    if args.replace is not None:
        old, new = args.replace
        if not old:
            raise Error('The search string cannot be empty.')
        return message.replace(old.encode('utf-8'), new.encode('utf-8'))
    needle = args.remove_line.encode('utf-8')
    if not needle:
        raise Error('The line search string cannot be empty.')
    return b''.join(line for line in message.splitlines(keepends=True) if needle not in line)


def plan(repo, old, args):
    commits = text(repo, 'rev-list', '--reverse', '--topo-order', old).splitlines()
    selected = None
    if args.mode == 'single':
        selected = text(repo, 'rev-parse', '--verify', args.commit + '^{commit}')
        if selected not in commits:
            raise Error('The selected commit is not reachable from the current branch.')
    rows, affected = [], set()
    for oid in commits:
        raw = git(repo, 'cat-file', 'commit', oid)
        fields, before = split_commit(raw)
        after = transform(before, args) if selected is None or selected == oid else before
        if before != after and not after.strip():
            raise Error('The edit would leave an empty message for ' + oid)
        parents = [f[7:].decode('ascii') for f in fields if f.startswith(b'parent ')]
        rewritten = before != after or any(p in affected for p in parents)
        if rewritten:
            affected.add(oid)
        rows.append((oid, fields, before, after, rewritten))
    return rows


def preview(rows):
    changed = [r for r in rows if r[2] != r[3]]
    for oid, fields, before, after, _ in changed:
        print('\nCommit ' + oid)
        a = before.decode('utf-8', 'backslashreplace').splitlines(keepends=True)
        b = after.decode('utf-8', 'backslashreplace').splitlines(keepends=True)
        print(''.join(difflib.unified_diff(a, b, fromfile='old message', tofile='new message')), end='\n')
    signed = sum(any(f.split(b' ', 1)[0] in (b'gpgsig', b'gpgsig-sha256', b'mergetag') for f in r[1]) for r in rows if r[4])
    print(f'\nMessages changed: {len(changed)}; commits receiving new IDs: {sum(r[4] for r in rows)}')
    if signed:
        print(f'Signature/mergetag headers will be removed from {signed} rewritten commits.')
    return bool(changed)


def rewrite(repo, rows):
    mapping = {}
    for oid, fields, before, after, affected in rows:
        if not affected:
            mapping[oid] = oid
            continue
        result = []
        for field in fields:
            key = field.split(b' ', 1)[0]
            if key in (b'gpgsig', b'gpgsig-sha256', b'mergetag'):
                continue
            if key == b'parent':
                parent = field[7:].decode('ascii')
                field = b'parent ' + mapping.get(parent, parent).encode('ascii')
            # A replacement message is UTF-8; remove a conflicting encoding declaration.
            if key == b'encoding' and before != after:
                try:
                    after.decode('utf-8')
                    continue
                except UnicodeDecodeError:
                    pass
            result.append(field)
        new = git(repo, 'hash-object', '-t', 'commit', '-w', '--stdin',
                  data=b'\n'.join(result) + b'\n\n' + after).decode().strip()
        # Verify exact tree, message, parent order, author and committer metadata.
        actual_fields, actual_msg = split_commit(git(repo, 'cat-file', 'commit', new))
        if actual_fields != result or actual_msg != after:
            raise Error('Commit verification failed; branch has not been changed.')
        mapping[oid] = new
    return mapping


def confirm(phrase):
    try:
        return input(f'\nType {phrase} to continue: ').strip() == phrase
    except EOFError:
        return False


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('repo', type=pathlib.Path, help='Path to the local clone')
    sub = p.add_subparsers(dest='mode', required=True)
    for mode in ('single', 'bulk'):
        s = sub.add_parser(mode)
        if mode == 'single':
            s.add_argument('--commit', required=True, help='Commit SHA or reference')
        edit = s.add_mutually_exclusive_group(required=True)
        edit.add_argument('--replace', nargs=2, metavar=('OLD', 'NEW'), help='Literal, case-sensitive replacement')
        edit.add_argument('--remove-line', help='Remove every message line containing this literal text')
        edit.add_argument('--message', help='Replace the entire message (all reachable commits in bulk mode)')
        s.add_argument('--apply', action='store_true', help='Ask to apply, then optionally ask to push')
        s.add_argument('--remote', default='origin', help='Remote to offer for push (default: origin)')
        s.add_argument('--local-only', action='store_true', help='Do not contact a remote or offer a push')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    repo = args.repo.expanduser().resolve()
    if args.remote.startswith('-'):
        raise Error('Invalid remote name.')
    if text(repo, 'rev-parse', '--is-bare-repository') == 'true':
        raise Error('Use a working clone, not a bare repository.')
    ref = text(repo, 'symbolic-ref', '-q', 'HEAD')
    old = text(repo, 'rev-parse', '--verify', 'HEAD')
    if text(repo, 'rev-parse', '--is-shallow-repository') == 'true':
        raise Error('Use a full clone; shallow history is not supported.')
    if text(repo, 'replace', '-l'):
        raise Error('Remove Git replace references before rewriting history.')
    grafts = pathlib.Path(text(repo, 'rev-parse', '--git-path', 'info/grafts'))
    if not grafts.is_absolute():
        grafts = repo / grafts
    if grafts.exists() and grafts.read_bytes().strip():
        raise Error('Legacy grafts are not supported.')
    for state in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer'):
        path = pathlib.Path(text(repo, 'rev-parse', '--git-path', state))
        if not path.is_absolute():
            path = repo / path
        if path.exists():
            raise Error('Finish or abort the in-progress Git operation first.')
    if git(repo, 'status', '--porcelain'):
        raise Error('Commit or stash working-directory changes, including untracked files, first.')
    print(f'Repository: {repo}\nBranch: {ref[11:]}\nOriginal tip: {old}')
    rows = plan(repo, old, args)
    if not preview(rows):
        print('Nothing to change.')
        return 0
    if not args.apply:
        print('\nPreview only. Run again with --apply to review and confirm changes.')
        return 0
    push_url = None
    if not args.local_only:
        push_url = text(repo, 'remote', 'get-url', '--push', '--all', args.remote)
        if len(push_url.splitlines()) != 1:
            raise Error('Exactly one push URL is required; use --local-only otherwise.')
        remote_rows = text(repo, 'ls-remote', '--refs', push_url, ref).splitlines()
        if len(remote_rows) != 1 or remote_rows[0].split()[0] != old:
            raise Error('Remote branch must exactly match the local tip before applying. Sync the clone, or use --local-only.')
        print(f'Push destination: remote {args.remote}, branch {ref[11:]}')
    if not confirm('APPLY'):
        print('Cancelled; branch unchanged.')
        return 0
    if text(repo, 'symbolic-ref', '-q', 'HEAD') != ref or text(repo, 'rev-parse', ref) != old or git(repo, 'status', '--porcelain'):
        raise Error('Repository changed during review. Run the command again.')
    mapping = rewrite(repo, rows)
    new = mapping[old]
    if text(repo, 'rev-parse', old + '^{tree}') != text(repo, 'rev-parse', new + '^{tree}'):
        raise Error('Tree validation failed; branch unchanged.')
    if text(repo, 'rev-list', '--count', old) != text(repo, 'rev-list', '--count', new):
        raise Error('Commit-count validation failed; branch unchanged.')
    backup = 'refs/heads/message-backup-' + uuid.uuid4().hex[:12]
    # Create the backup and move the branch together, only if the tip is still old.
    transaction = f'start\ncreate {backup} {old}\nupdate {ref} {new} {old}\nprepare\ncommit\n'
    git(repo, 'update-ref', '-m', 'Reviewed commit message rewrite', '--stdin', data=transaction.encode())
    print(f'\nApplied and validated. File contents and commit count are unchanged.\nNew tip: {new}\nBackup branch: {backup[11:]}')
    print('Other branches and tags have not been moved. Keep the backup until satisfied.')
    if push_url is None:
        return 0
    print(f'\nReady to replace {args.remote}/{ref[11:]} with the validated history.\nCollaborators will need to sync to the rewritten history.')
    if not confirm('PUSH ' + ref[11:]):
        print('Not pushed. Local rewrite and backup remain available.')
        return 0
    if text(repo, 'rev-parse', ref) != new:
        raise Error('Branch moved after validation; push cancelled.')
    git(repo, 'push', '--force-with-lease=' + ref + ':' + old, push_url, new + ':' + ref)
    remote_tip = text(repo, 'ls-remote', '--refs', push_url, ref).split()
    if not remote_tip or remote_tip[0] != new:
        raise Error('Push finished but remote verification did not match; inspect the remote before retrying.')
    print('Pushed and verified on the remote.')
    return 0


def cli():
    try:
        sys.exit(main())
    except (Error, UnicodeError, OSError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nInterrupted. Inspect the branch and backup before continuing.', file=sys.stderr)
        sys.exit(130)
