"""Spec §12 rows that need no adapter: digest, copy with staging and rollback, SIGINT, the lock,
the version gate, credential redaction, the state file's true no-op, the report and exit codes."""

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

A = support.load_script()


def make_tree(root, files):
    for rel, text in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
    return root


def read_tree(root):
    out = {}
    for d, _, names in os.walk(root):
        for n in names:
            p = os.path.join(d, n)
            with open(p) as f:
                out[os.path.relpath(p, root)] = f.read()
    return out


class Digest(support.SandboxCase, unittest.TestCase):
    def test_digest_covers_paths_and_bytes_and_skips_dot_names(self):
        a = make_tree(os.path.join(self.sb.root, "a"), {"SKILL.md": "x", "ref/b.md": "y"})
        b = make_tree(os.path.join(self.sb.root, "b"), {"SKILL.md": "x", "ref/b.md": "y",
                                                         ".DS_Store": "z", ".git/HEAD": "h"})
        self.assertEqual(A.digest_tree(a), A.digest_tree(b))
        self.assertEqual(A.digest_tree(a)[1], 2)
        make_tree(b, {"ref/b.md": "changed"})
        self.assertNotEqual(A.digest_tree(a)[0], A.digest_tree(b)[0])
        os.rename(os.path.join(b, "ref", "b.md"), os.path.join(b, "ref", "c.md"))
        make_tree(b, {"ref/c.md": "y"})
        self.assertNotEqual(A.digest_tree(a)[0], A.digest_tree(b)[0], "a rename changes it")

    def test_a_symlink_anywhere_is_refused(self):
        a = make_tree(os.path.join(self.sb.root, "a"), {"SKILL.md": "x"})
        os.makedirs(os.path.join(a, "deep"))
        os.symlink("/etc/hosts", os.path.join(a, "deep", "link"))
        with self.assertRaises(A.SymlinkError) as cm:
            A.digest_tree(a)
        self.assertIn("deep/link", str(cm.exception))

    def test_the_source_itself_may_not_be_a_symlink(self):
        a = make_tree(os.path.join(self.sb.root, "a"), {"SKILL.md": "x"})
        os.symlink(a, os.path.join(self.sb.root, "via-link"))
        with self.assertRaises(A.SymlinkError):
            A.digest_tree(os.path.join(self.sb.root, "via-link"))


class InstallTree(support.SandboxCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.sb.home, ".gemini", "config")
        self.dest = os.path.join(self.config, "skills", "s")
        self.stage = os.path.join(self.config, ".agent-sync-stage")
        self.old = os.path.join(self.config, ".agent-sync-old")
        self.archive = os.path.join(self.sb.state_dir, "archive", "T", "agy", "s")
        self.src = make_tree(os.path.join(self.sb.root, "src"), {"SKILL.md": "new",
                                                                  "ref/a.md": "a"})
        self.rename = A._rename
        self.addCleanup(setattr, A, "_rename", self.rename)

    def install(self):
        return A.install_tree(self.src, self.dest, self.stage, self.archive, self.old)

    def test_first_copy(self):
        got = self.install()
        self.assertEqual(read_tree(self.dest), {"SKILL.md": "new", "ref/a.md": "a"})
        self.assertEqual(got["digest"], A.digest_tree(self.src)[0])
        self.assertEqual(got["files"], 2)
        self.assertIsNone(got["archived"])
        self.assertFalse(os.path.exists(self.stage), "the staging folder is removed")

    def test_replacement_archives_the_old_tree(self):
        make_tree(self.dest, {"SKILL.md": "old"})
        got = self.install()
        self.assertEqual(read_tree(self.dest)["SKILL.md"], "new")
        self.assertEqual(read_tree(self.archive), {"SKILL.md": "old"})
        self.assertEqual(got["archived"], self.archive)

    def test_dot_names_are_not_copied(self):
        make_tree(self.src, {".hidden": "h"})
        self.install()
        self.assertNotIn(".hidden", read_tree(self.dest))

    def test_symlink_in_source_writes_nothing(self):
        os.symlink("/etc/hosts", os.path.join(self.src, "link"))
        with self.assertRaises(A.TreeError):
            self.install()
        self.assertFalse(os.path.exists(self.dest))
        self.assertFalse(os.path.exists(self.stage))

    def test_rename_failure_at_the_swap_restores_the_old_tree(self):
        make_tree(self.dest, {"SKILL.md": "old"})
        calls = []

        def failing(a, b):
            calls.append((a, b))
            if len(calls) == 2:  # stage -> destination
                raise OSError(5, "injected")
            return self.rename(a, b)

        A._rename = failing
        with self.assertRaises(A.TreeError) as cm:
            self.install()
        self.assertIn("restored", str(cm.exception))
        self.assertEqual(read_tree(self.dest), {"SKILL.md": "old"})
        self.assertFalse(os.path.exists(self.archive))

    def test_failed_restore_names_both_paths(self):
        make_tree(self.dest, {"SKILL.md": "old"})
        calls = []

        def failing(a, b):
            calls.append((a, b))
            if len(calls) >= 2:
                raise OSError(5, "injected")
            return self.rename(a, b)

        A._rename = failing
        with self.assertRaises(A.TreeError) as cm:
            self.install()
        msg = str(cm.exception)
        self.assertIn(self.archive, msg)
        self.assertIn(self.stage, msg)
        self.assertEqual(read_tree(self.archive), {"SKILL.md": "old"}, "nothing is lost")

    def test_archive_on_another_filesystem_goes_through_the_old_folder(self):
        make_tree(self.dest, {"SKILL.md": "old"})
        seen = []

        def cross_device(a, b):
            seen.append(b)
            if b == self.archive:
                raise OSError(18, "Cross-device link")  # EXDEV
            return self.rename(a, b)

        A._rename = cross_device
        self.install()
        self.assertTrue(any(p.startswith(self.old + os.sep) for p in seen))
        self.assertEqual(read_tree(self.archive), {"SKILL.md": "old"})
        self.assertEqual(read_tree(self.dest)["SKILL.md"], "new")
        self.assertFalse(os.path.exists(self.old))

    def test_sigint_during_the_swap_leaves_old_or_new_never_neither(self):
        make_tree(self.dest, {"SKILL.md": "old"})
        calls = []

        def interrupting(a, b):
            calls.append(b)
            result = self.rename(a, b)
            if len(calls) == 1:  # the destination has just been moved away
                os.kill(os.getpid(), signal.SIGINT)
            return result

        A._rename = interrupting
        with self.assertRaises(KeyboardInterrupt):
            self.install()
        self.assertEqual(read_tree(self.dest)["SKILL.md"], "new")
        self.assertEqual(read_tree(self.archive), {"SKILL.md": "old"})


class StateFile(support.SandboxCase, unittest.TestCase):
    def test_round_trip_and_true_no_op(self):
        path = os.path.join(self.sb.state_dir, "state.json")
        st = A.State(path)
        self.assertEqual(st.data["agy"], {})
        st.data["agy"]["s"] = {"digest": "d"}
        self.assertTrue(st.save())
        mtime = os.stat(path).st_mtime_ns
        st2 = A.State(path)
        self.assertEqual(st2.data["agy"]["s"], {"digest": "d"})
        self.assertFalse(st2.save(), "an unchanged state is not rewritten")
        self.assertEqual(os.stat(path).st_mtime_ns, mtime)
        self.assertEqual([n for n in os.listdir(self.sb.state_dir)], ["state.json"],
                         "no temp file is left behind")

    def test_nothing_is_created_when_nothing_changes(self):
        path = os.path.join(self.sb.state_dir, "state.json")
        self.assertFalse(A.State(path).save())
        self.assertFalse(os.path.exists(self.sb.state_dir))

    def test_unreadable_state_is_a_usage_error(self):
        os.makedirs(self.sb.state_dir)
        path = os.path.join(self.sb.state_dir, "state.json")
        with open(path, "w") as f:
            f.write("{not json")
        with self.assertRaises(A.UsageError):
            A.State(path)


class Runner(support.SandboxCase, unittest.TestCase):
    def test_stdin_closed_argv_list_and_logged_with_credentials_redacted(self):
        with self.sb.active():
            runner = A.Runner()
            r = runner.run(["git", "clone", "--no-checkout",
                            "https://user:secret-token@localhost/a/b.git", "/nonexistent"])
        self.assertNotEqual(r.returncode, 0)
        call = self.sb.calls("git")[0]
        self.assertFalse(call["stdin_tty"])
        log = os.path.join(self.sb.root, "last-run.log")
        runner.write_log(log)
        with open(log) as f:
            text = f.read()
        self.assertNotIn("secret-token", text)
        self.assertIn("https://***@localhost/a/b.git", text)

    def test_redact(self):
        self.assertEqual(A.redact("x https://u:p@h/r ssh://git@h/r https://h/r"),
                         "x https://***@h/r ssh://***@h/r https://h/r")

    def test_missing_binary_and_timeout(self):
        with self.sb.active():
            runner = A.Runner()
            r = runner.run(["no-such-tool"])
            self.assertTrue(r.missing)
            self.assertIn("not found", r.error())
            slow = os.path.join(self.sb.bin, "slow")
            with open(slow, "w") as f:
                f.write("#!/bin/sh\nexec /bin/sleep 5\n")
            os.chmod(slow, 0o755)
            r = runner.run(["slow"], timeout=0.5)
            self.assertTrue(r.timed_out)
            self.assertIn("timed out after 0.5 s", r.error())

    def test_extra_env_reaches_only_that_call(self):
        with self.sb.active():
            runner = A.Runner()
            runner.run(["agy", "plugin", "list", "--json"],
                       extra_env={"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
            runner.run(["agy", "plugin", "list", "--json"])
        self.assertEqual([c["nonessential_traffic"] for c in self.sb.calls("agy")], ["1", None])


class LockAndGate(support.SandboxCase, unittest.TestCase):
    MANIFEST = 'version = 1\nharnesses = ["agy"]\n'

    def test_second_run_exits_4_naming_the_pid(self):
        self.sb.manifest(self.MANIFEST)
        os.makedirs(self.sb.state_dir)
        path = os.path.join(self.sb.state_dir, "lock")
        with open(path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            f.write("4242\n")
            f.flush()
            r = self.sb.run()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("PID 4242", r.stderr)
        self.assertEqual(self.sb.calls(), [], "nothing ran")

    def test_a_stale_lock_file_does_not_block(self):
        self.sb.manifest(self.MANIFEST)
        os.makedirs(self.sb.state_dir)
        with open(os.path.join(self.sb.state_dir, "lock"), "w") as f:
            f.write("4242\n")
        r = self.sb.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_dry_run_takes_no_lock_and_writes_nothing(self):
        self.sb.manifest(self.MANIFEST)
        r = self.sb.run("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.sb.state_dir))
        self.assertFalse(os.path.exists(self.sb.cache_home))

    def test_version_gate(self):
        with self.assertRaises(SystemExit) as cm:
            A.version_gate((3, 10))
        self.assertEqual(cm.exception.code, 4)
        A.version_gate((3, 11))

    @unittest.skipUnless(os.path.exists("/usr/bin/python3"), "no system python3")
    def test_version_gate_on_the_system_python(self):
        v = subprocess.run(["/usr/bin/python3", "-c", "import sys; print(sys.version_info[1])"],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if v.returncode != 0 or int(v.stdout) >= 11:
            self.skipTest("the system python3 has tomllib")
        r = subprocess.run(["/usr/bin/python3", support.SCRIPT, "--dry-run"],
                           env=self.sb.env(), capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 4)
        self.assertIn("needs Python 3.11", r.stderr)


class Report(unittest.TestCase):
    def report(self, *rows, **kw):
        rep = A.Report()
        for r in rows:
            rep.add(*r)
        return rep

    def test_exit_codes(self):
        self.assertEqual(self.report(("claude", "a", "unchanged", "")).exit_code(), 0)
        self.assertEqual(self.report(("claude", "a", "duplicate", ""),
                                     ("-", "b", "available", ""),
                                     ("codex", "c", "unverifiable", ""),
                                     ("claude", "d", "unmanaged", "")).exit_code(), 0)
        self.assertEqual(self.report(("claude", "a", "held", "")).exit_code(), 3)
        self.assertEqual(self.report(("claude", "a", "held", ""),
                                     ("codex", "b", "stale", "")).exit_code(), 1)
        self.assertEqual(self.report(("claude", "a", "held", ""),
                                     ("agy", "b", "failed", "")).exit_code(), 1)
        self.assertEqual(self.report(("claude", "a", "failed", "")).exit_code(interrupted=True),
                         130)

    def test_check_exit_codes(self):
        quiet = ("unchanged", "live", "external", "unmanaged", "available")
        rep = self.report(*[("claude", r, r, "") for r in quiet])
        self.assertEqual(rep.exit_code(check=True), 0)
        for drift in ("unchecked", "held", "duplicate", "orphaned", "unverifiable"):
            rep = self.report(("claude", "a", "unchanged", ""), ("claude", "b", drift, ""))
            self.assertEqual(rep.exit_code(check=True), 1, drift)

    def test_table_layout(self):
        rep = self.report(
            ("claude", "marketplace example-skills", "live", "checkout 3f2a91c (clean)"),
            ("claude", "editor-integration@example-vendor-plugins", "held",
             "declared command awaits confirmation:\n`npx x`"),
            ("-", "linting@example-vendor-plugins", "available", "in the catalog"))
        lines = rep.table().splitlines()
        self.assertEqual(lines[0], "HARNESS  ITEM                                   RESULT       "
                                   "DETAIL")
        self.assertEqual(lines[1], "claude   marketplace example-skills             live         "
                                   "checkout 3f2a91c (clean)")
        self.assertEqual(lines[2], "claude   editor-integration@example-vendor-…    held         "
                                   "declared command awaits confirmation:")
        self.assertEqual(lines[3], " " * 63 + "`npx x`")
        self.assertEqual(lines[4][:9], "-        ")

    def test_summary_and_next(self):
        rep = self.report(("claude", "a", "installed", ""), ("codex", "b", "updated", ""),
                          ("agy", "c", "copied", ""), ("claude", "d", "unchanged", ""),
                          ("claude", "e", "live", ""), ("claude", "f", "held", ""),
                          ("codex", "g", "stale", ""), ("codex", "h", "duplicate", ""),
                          ("-", "i", "available", ""), ("agy", "j", "orphaned", ""))
        text = rep.footer()
        self.assertIn("Summary: 3 changed · 1 unchanged · 1 live · 1 held · 1 stale · "
                      "1 duplicate · 0 failed · 1 orphaned", text)
        self.assertIn("Next:    restart Claude Code sessions or run /reload-plugins · "
                      "restart Codex sessions ·\n         run /skills reload in agy", text)
        self.assertIn("Exit 1", text)

    def test_json_lines(self):
        rep = self.report(("claude", "p@m", "held", "line one\nline two"))
        rep.rows[0].extra["sha256"] = "a" * 64
        lines = [json.loads(x) for x in rep.json_lines(0).splitlines()]
        self.assertEqual(lines[0], {"harness": "claude", "item": "p@m", "result": "held",
                                    "detail": "line one\nline two", "sha256": "a" * 64})
        self.assertEqual(lines[-1]["exit"], 0)
        self.assertEqual(lines[-1]["summary"]["held"], 1)


if __name__ == "__main__":
    unittest.main()
