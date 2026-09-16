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
        self.repo = pathlib.Path(self.temp.name) / 'repo'
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
        with (self.repo / name).open('a') as f:
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
        remote = pathlib.Path(self.temp.name) / 'remote.git'
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


if __name__ == '__main__':
    unittest.main()
