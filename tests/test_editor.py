import os
import sys
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from git_rewrite import cli as editor


class RewriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Isolate tests from user signing, hooks, line-ending, and alias settings.
        config = pathlib.Path(self.temp.name) / 'empty.gitconfig'
        config.write_text('', encoding='utf-8')
        environment = patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': str(config), 'GIT_CONFIG_NOSYSTEM': '1'})
        environment.start()
        self.addCleanup(environment.stop)
        self.repo = pathlib.Path(self.temp.name) / 'repo with spaces café'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test User')
        self.git('config', 'user.email', 'test@example.com')
        self.commit('First\n\nCo-authored-by: Claude <claude@example.com>')
        self.first = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-b', 'side')
        self.commit('Side', 'side.txt')
        self.git('checkout', 'main')
        self.commit('Main\n\nCo-authored-by: Claude <claude@example.com>')
        self.git('merge', '--no-ff', 'side', '-m', 'Merge side')
        self.old = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return editor.text(self.repo, *args)

    def commit(self, msg, name='file.txt'):
        with (self.repo / name).open('a', encoding='utf-8', newline='\n') as f:
            f.write(msg + '\n')
        self.git('add', name)
        self.git('commit', '-m', msg)

    def args(self, *args):
        return editor.parser().parse_args([str(self.repo), *args])

    def test_bulk_preserves_graph_and_metadata(self):
        rows = editor.plan(self.repo, self.old, self.args('bulk', '--remove-line', 'Co-authored-by: Claude'))
        mapping = editor.rewrite(self.repo, rows)
        for old, new in mapping.items():
            a, am = editor.split_commit(editor.git(self.repo, 'cat-file', 'commit', old))
            b, bm = editor.split_commit(editor.git(self.repo, 'cat-file', 'commit', new))
            self.assertEqual([f for f in a if not f.startswith(b'parent ')], [f for f in b if not f.startswith(b'parent ')])
            self.assertEqual([b'parent ' + mapping[f[7:].decode()].encode() for f in a if f.startswith(b'parent ')], [f for f in b if f.startswith(b'parent ')])
            self.assertNotIn(b'Co-authored-by: Claude', bm)
        self.assertEqual(self.git('rev-list', '--count', self.old), self.git('rev-list', '--count', mapping[self.old]))

    def test_single_only_changes_selected_message(self):
        rows = editor.plan(self.repo, self.old, self.args('single', '--commit', self.first, '--message', 'New first'))
        self.assertEqual([r[0] for r in rows if r[2] != r[3]], [self.first])
        self.assertEqual(sum(r[4] for r in rows), 4)

    def test_preview_and_decline_do_not_move_branch(self):
        editor.main([str(self.repo), 'bulk', '--replace', 'Claude', 'Custom'])
        with patch('builtins.input', return_value='NO'):
            editor.main([str(self.repo), 'bulk', '--replace', 'Claude', 'Custom', '--apply', '--local-only'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)

    def remote(self):
        remote = pathlib.Path(self.temp.name) / 'remote with spaces café.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(remote))
        self.git('push', 'origin', 'main')
        return remote

    def test_apply_backup_and_push(self):
        remote = self.remote()
        with patch('builtins.input', side_effect=['APPLY', 'PUSH main']):
            editor.main([str(self.repo), 'bulk', '--replace', 'Claude', 'Custom', '--apply'])
        new = self.git('rev-parse', 'HEAD')
        self.assertNotEqual(new, self.old)
        self.assertEqual(editor.text(remote, 'rev-parse', 'main'), new)
        self.assertEqual(self.git('for-each-ref', '--format=%(objectname)', 'refs/heads/message-backup-*'), self.old)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_remote_race_rejected(self):
        remote = self.remote()
        def reply(prompt):
            if 'APPLY' in prompt:
                return 'APPLY'
            editor.git(remote, 'update-ref', 'refs/heads/main', self.first)
            return 'PUSH main'
        with patch('builtins.input', side_effect=reply), self.assertRaises(editor.Error):
            editor.main([str(self.repo), 'bulk', '--replace', 'Claude', 'Custom', '--apply'])
        self.assertEqual(editor.text(remote, 'rev-parse', 'main'), self.first)
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), self.old)

    def test_dirty_clone_rejected(self):
        (self.repo / 'untracked').write_text('work')
        with self.assertRaises(editor.Error):
            editor.main([str(self.repo), 'bulk', '--message', 'New'])


    def test_message_file_bom_crlf_and_unicode(self):
        message = pathlib.Path(self.temp.name) / 'message with spaces.txt'
        message.write_bytes(b'\xef\xbb\xbf' + 'Fix café 🚀\r\n\r\nDetails\r\n'.encode('utf-8'))
        with patch('builtins.input', return_value='APPLY'):
            editor.main([str(self.repo), 'single', '--commit', 'HEAD', '--message-file', str(message), '--apply', '--local-only'])
        _, body = editor.split_commit(editor.git(self.repo, 'cat-file', 'commit', 'HEAD'))
        self.assertEqual(body, 'Fix café 🚀\n\nDetails\n'.encode('utf-8'))

    def test_crlf_working_files_unchanged(self):
        self.git('config', 'core.autocrlf', 'true')
        target = self.repo / 'windows.txt'
        target.write_bytes(b'first\r\nsecond\r\n')
        self.git('add', 'windows.txt')
        self.git('commit', '-m', 'Windows Claude')
        original = target.read_bytes()
        tree = self.git('rev-parse', 'HEAD^{tree}')
        with patch('builtins.input', return_value='APPLY'):
            editor.main([str(self.repo), 'bulk', '--replace', 'Claude', 'Custom', '--apply', '--local-only'])
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(self.git('rev-parse', 'HEAD^{tree}'), tree)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_cli_legacy_console_encoding(self):
        env = dict(os.environ, PYTHONIOENCODING='cp1252:strict')
        result = subprocess.run([sys.executable, '-m', 'git_rewrite', str(self.repo), 'single', '--commit', 'HEAD', '--message', 'Fix 🚀'], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'Preview only', result.stdout)
        self.assertIn(b'\\U0001f680', result.stdout)

    def test_missing_git_has_actionable_error(self):
        with patch.object(editor.subprocess, 'run', side_effect=FileNotFoundError):
            with self.assertRaisesRegex(editor.Error, 'Install Git'):
                editor.git(self.repo, 'status')

    def test_git_arguments_are_not_shell_commands(self):
        message = 'Quotes "here" & $HOME; echo test | more %PATH%'
        with patch('builtins.input', return_value='APPLY'):
            editor.main([str(self.repo), 'single', '--commit', 'HEAD', '--message', message, '--apply', '--local-only'])
        _, body = editor.split_commit(editor.git(self.repo, 'cat-file', 'commit', 'HEAD'))
        self.assertEqual(body, (message + '\n').encode())

    def test_push_does_not_follow_tags(self):
        remote = self.remote()
        self.git('tag', '-a', 'local-tag', self.first, '-m', 'Keep local')
        self.git('config', 'push.followTags', 'true')
        with patch('builtins.input', side_effect=['APPLY', 'PUSH main']):
            editor.main([str(self.repo), 'single', '--commit', 'HEAD', '--message', 'New merge', '--apply'])
        self.assertEqual(editor.text(remote, 'tag', '--list'), '')

    def test_empty_message_is_rejected_without_moving_branch(self):
        with self.assertRaises(editor.Error):
            editor.main([str(self.repo), 'single', '--commit', 'HEAD', '--message', '', '--apply', '--local-only'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)

    def test_linked_worktree(self):
        linked = pathlib.Path(self.temp.name) / 'linked worktree'
        self.git('worktree', 'add', '-b', 'linked', str(linked))
        with patch('builtins.input', return_value='APPLY'):
            editor.main([str(linked), 'single', '--commit', 'HEAD', '--message', 'Linked message', '--apply', '--local-only'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)
        self.assertNotEqual(editor.text(linked, 'rev-parse', 'HEAD'), self.old)
        self.assertEqual(editor.text(linked, 'status', '--porcelain'), '')



    def test_no_match_does_not_write_backup(self):
        editor.main([str(self.repo), 'bulk', '--replace', 'not-present', 'replacement', '--apply', '--local-only'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)
        self.assertEqual(self.git('for-each-ref', '--format=%(refname)', 'refs/heads/message-backup-*'), '')

    def test_detached_head_and_in_progress_merge_rejected(self):
        self.git('checkout', '--detach')
        with self.assertRaises(editor.Error):
            editor.main([str(self.repo), 'bulk', '--message', 'New'])
        self.git('checkout', 'main')
        merge_head = self.repo / '.git' / 'MERGE_HEAD'
        merge_head.write_text(self.first + '\n', encoding='ascii')
        with self.assertRaisesRegex(editor.Error, 'in-progress'):
            editor.main([str(self.repo), 'bulk', '--message', 'New'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)

    def test_remote_mismatch_before_apply_leaves_branch_unchanged(self):
        remote = self.remote()
        editor.git(remote, 'update-ref', 'refs/heads/main', self.first)
        with self.assertRaisesRegex(editor.Error, 'exactly match'):
            editor.main([str(self.repo), 'bulk', '--replace', 'Claude', 'Custom', '--apply'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)

    def test_decline_push_retains_local_backup(self):
        remote = self.remote()
        with patch('builtins.input', side_effect=['APPLY', 'NO']):
            editor.main([str(self.repo), 'bulk', '--replace', 'Claude', 'Custom', '--apply'])
        self.assertEqual(editor.text(remote, 'rev-parse', 'main'), self.old)
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), self.old)
        self.assertEqual(self.git('for-each-ref', '--format=%(objectname)', 'refs/heads/message-backup-*'), self.old)

    def test_signature_headers_removed_only_on_rewritten_commit(self):
        fields, message = editor.split_commit(editor.git(self.repo, 'cat-file', 'commit', self.old))
        signed = fields + [b'gpgsig -----BEGIN PGP SIGNATURE-----\n test\n -----END PGP SIGNATURE-----']
        raw = b'\n'.join(signed) + b'\n\n' + message
        oid = editor.git(self.repo, 'hash-object', '-t', 'commit', '-w', '--stdin', data=raw).decode().strip()
        args = self.args('single', '--commit', oid, '--message', 'Changed')
        rows = editor.plan(self.repo, oid, args)
        mapping = editor.rewrite(self.repo, rows)
        actual, body = editor.split_commit(editor.git(self.repo, 'cat-file', 'commit', mapping[oid]))
        self.assertFalse(any(f.startswith(b'gpgsig ') for f in actual))
        self.assertEqual(body, b'Changed\n')
        self.assertEqual(editor.git(self.repo, 'cat-file', 'commit', oid), raw)


if __name__ == '__main__':
    unittest.main()
