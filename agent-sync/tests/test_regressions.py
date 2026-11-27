"""Regression tests for the first review's findings: each one fails on the reviewed head.

B1-B11 are its blocking findings, SF2-SF8 the should-fix ones it named; SF1's no-op rule is in
test_end_to_end.Combinations. Every case runs in a sandbox, against the fakes."""

import contextlib
import errno
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scenario  # noqa: E402
import support  # noqa: E402
from support import find, rows  # noqa: E402

A = support.load_script()
STAMP = "2026-01-02T03-04-05"


def loose(sb, *skills):
    """A manifest copying loose skills, given as (name, path), to agy only."""
    sb.manifest("version = 1\nharnesses = [\"agy\"]\n" + "".join(
        '[[skill]]\nname = "%s"\npath = "%s"\n' % s for s in skills))


def write_state(sb, doc):
    os.makedirs(sb.state_dir, exist_ok=True)
    with open(os.path.join(sb.state_dir, "state.json"), "w") as f:
        json.dump(dict({"version": 1, "agy": {}, "applied": {}, "cleanup": {}}, **doc), f)


def read_state(sb):
    with open(os.path.join(sb.state_dir, "state.json")) as f:
        return json.load(f)


def in_process(sb, argv, rename=None):
    """main() in this process, with the rename primitive optionally replaced."""
    real = A._rename
    if rename:
        A._rename = rename(real)
    try:
        with sb.active(), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return A.main(argv)
    finally:
        A._rename = real


def restore_stamp(result):
    return result.stdout.rsplit("--restore ", 1)[1].strip()


class Paths(support.SandboxCase, unittest.TestCase):
    """B1, B2, B6: nothing agent-sync writes is reached through a link or a stored path."""

    def setUp(self):
        super().setUp()
        self.src = os.path.join(self.sb.home, "src", "review-note")
        scenario.write_skill(self.src, "review-note")
        loose(self.sb, ("review-note", self.src))

    def test_b1_a_state_key_naming_a_path_is_refused_before_anything_moves(self):
        victim = os.path.join(self.sb.home, "victim")
        scenario.write_skill(victim, "victim")
        write_state(self.sb, {"agy": {"../../../victim": {"digest": "d"}}})
        r = self.sb.run("--prune")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("move it aside to start over", r.stderr)
        self.assertTrue(os.path.isdir(victim))

    def test_b1_a_cleanup_record_holding_paths_is_refused(self):
        victim = os.path.join(self.sb.home, "victim")
        scenario.write_skill(victim, "victim")
        write_state(self.sb, {"cleanup": {STAMP: [{"harness": "claude", "name": "x",
                                                   "from": os.path.join(self.sb.home, "moved"),
                                                   "to": victim}]}})
        r = self.sb.run("cleanup", "--restore", STAMP)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(os.path.isdir(victim))
        self.assertFalse(os.path.exists(os.path.join(self.sb.home, "moved")))

    def test_b2_a_symlinked_stage_folder_is_refused_and_nothing_lands_beyond_it(self):
        outside = os.path.join(self.sb.home, "unrelated")
        os.makedirs(outside)
        stage = os.path.join(os.path.dirname(self.sb.agy_skills), ".agent-sync-stage")
        os.makedirs(os.path.dirname(stage))
        os.symlink(outside, stage)
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        row = find(rows(r)[0], "agy", "skills folder")[0]
        self.assertIn(".agent-sync-stage is a symlink", row["detail"])
        self.assertEqual(os.listdir(outside), [])

    def test_b2_a_symlinked_lock_is_refused_and_its_target_untouched(self):
        victim = os.path.join(self.sb.home, "victim.txt")
        with open(victim, "w") as f:
            f.write("keep me")
        os.makedirs(self.sb.state_dir)
        os.symlink(victim, os.path.join(self.sb.state_dir, "lock"))
        r = self.sb.run()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        with open(victim) as f:
            self.assertEqual(f.read(), "keep me")

    def test_b2_a_planted_temp_path_does_not_redirect_the_state_write(self):
        victim = os.path.join(self.sb.home, "victim.txt")
        with open(victim, "w") as f:
            f.write("keep me")
        os.makedirs(self.sb.state_dir)
        # In this process, so the pid in a predictable temp name is known.
        os.symlink(victim, os.path.join(self.sb.state_dir, "state.json.tmp.%d" % os.getpid()))
        self.assertEqual(in_process(self.sb, []), 0)
        with open(victim) as f:
            self.assertEqual(f.read(), "keep me")
        self.assertIn("review-note", read_state(self.sb)["agy"])

    def test_b2_a_state_folder_reached_through_a_symlink_is_refused(self):
        elsewhere = os.path.join(self.sb.home, "elsewhere")
        os.makedirs(elsewhere)
        os.makedirs(self.sb.state_home)
        os.symlink(elsewhere, self.sb.state_dir)
        r = self.sb.run()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(os.listdir(elsewhere), [])

    def test_b6_the_lock_is_taken_before_the_state_is_read(self):
        order = []
        real_lock, real_state = A.Lock.__enter__, A.State.__init__

        def lock(self):
            order.append("lock")
            return real_lock(self)

        def state(self, *a, **k):
            order.append("state")
            return real_state(self, *a, **k)

        A.Lock.__enter__, A.State.__init__ = lock, state
        try:
            self.assertEqual(in_process(self.sb, []), 0)
        finally:
            A.Lock.__enter__, A.State.__init__ = real_lock, real_state
        self.assertEqual(order[:2], ["lock", "state"])


class GitCache(support.SandboxCase, unittest.TestCase):
    """B2, B3: the Git cache is confined, and materialises no symlink."""

    def setUp(self):
        super().setUp()
        scenario.setup(self.sb, harnesses='["claude"]')
        self.cache = os.path.join(self.sb.cache_home, "agent-sync", "sources",
                                  "example-vendor-plugins")

    def run_with(self, **extra):
        env = dict(self.sb.env(), **extra)
        return subprocess.run([sys.executable, support.SCRIPT, "--json"], env=env,
                              cwd=self.sb.root, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=60)

    def test_b2_git_never_sees_the_callers_repository_variables(self):
        other = os.path.join(self.sb.root, "other-repo")
        os.makedirs(other)
        r = self.run_with(GIT_DIR=other, GIT_WORK_TREE=other, GIT_INDEX_FILE="x")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.sb.calls("git"))
        for call in self.sb.calls("git"):
            self.assertEqual(call["git_env"], [], call["argv"])
        self.assertEqual(os.listdir(other), [])

    def test_b2_redirected_git_metadata_in_the_cache_fails_that_source(self):
        self.assertEqual(self.sb.run().returncode, 0)
        meta = os.path.join(self.cache, ".git")
        shutil.move(meta, meta + "-real")
        os.symlink(meta + "-real", meta)
        r = self.sb.run("--json")
        row = find(rows(r)[0], "claude", "marketplace example-vendor-plugins")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("redirected Git metadata", row["detail"])

    def test_b3_a_tracked_symlink_is_checked_out_as_a_plain_file(self):
        tree = scenario.move_remote(self.sb, scenario.VURL, "v2.3.0",
                                    os.path.join(support.FIXTURES, "catalog-shared"),
                                    support.sha(9))
        os.symlink("/etc/hosts", os.path.join(tree, "a-link"))
        r = self.sb.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        link = os.path.join(self.cache, "a-link")
        self.assertFalse(os.path.islink(link))
        with open(link) as f:
            self.assertEqual(f.read(), "/etc/hosts")


class Sources(support.SandboxCase, unittest.TestCase):
    """B3, B4: what a skill is read from, and what prune may conclude from a failure."""

    def test_b3_a_symlinked_plugin_folder_inside_a_catalog_is_not_read(self):
        scenario.setup(self.sb, harnesses='["agy"]')
        plugin = os.path.join(self.sb.home, "src", "example-skills", "plugins", "planning")
        outside = os.path.join(self.sb.home, "outside-catalog")
        os.rename(plugin, outside)
        os.symlink(outside, plugin)
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertFalse(os.path.lexists(os.path.join(self.sb.agy_skills, "framing-ideas")))
        self.assertIn("plugins/planning is a symlink",
                      find(rows(r)[0], "agy", "planning@example-skills")[0]["detail"])

    def test_b4_prune_leaves_a_skill_whose_source_could_not_be_read(self):
        scenario.setup(self.sb, harnesses='["agy"]', vendor_agy="git",
                       vendor_harnesses='["agy"]')
        copy = os.path.join(self.sb.agy_skills, "editor-setup")
        self.assertEqual(self.sb.run().returncode, 0)
        self.assertTrue(os.path.isdir(copy))
        del self.sb.config["remotes"][scenario.VURL]
        self.sb.save_config()
        r = self.sb.run("--prune", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(os.path.isdir(copy))
        self.assertIn("editor-setup", read_state(self.sb)["agy"])
        self.assertEqual(find(rows(r)[0], "agy", "editor-setup"), [])

    def test_b4_prune_leaves_the_skills_of_a_plugin_whose_subset_is_invalid(self):
        scenario.setup(self.sb, harnesses='["agy"]')
        self.assertEqual(self.sb.run().returncode, 0)
        manifest = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(manifest) as f:
            text = f.read()
        self.sb.manifest(text.replace('agy_skills = ["reviewing-code-changes"]',
                                      'agy_skills = ["no-such-skill"]'))
        r = self.sb.run("--prune", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(os.path.isdir(os.path.join(self.sb.agy_skills,
                                                   "reviewing-code-changes")))


class Interruption(support.SandboxCase, unittest.TestCase):
    """B5: the swap and its record are one operation; a failed transfer is recoverable."""

    def test_b5_sigint_inside_the_swap_records_the_copy_it_put_in_place(self):
        src = os.path.join(self.sb.home, "src", "review-note")
        scenario.write_skill(src, "review-note")
        loose(self.sb, ("review-note", src))
        self.assertEqual(self.sb.run().returncode, 0)
        scenario.write_skill(src, "review-note", "Updated")
        dest = os.path.join(self.sb.agy_skills, "review-note")

        def interrupting(real):
            def rename(a, b):
                real(a, b)
                if b == dest:
                    os.kill(os.getpid(), signal.SIGINT)
            return rename

        self.assertEqual(in_process(self.sb, [], interrupting), 130)
        with open(os.path.join(dest, "SKILL.md")) as f:
            self.assertIn("Updated", f.read())
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(find(rows(r)[0], "agy", "review-note")[0]["result"], "unchanged")

    def test_b5_a_failed_cross_device_transfer_names_where_the_old_copy_is(self):
        with self.sb.active():
            config = os.path.join(self.sb.home, ".gemini", "config")
            dest, src = os.path.join(config, "skills", "s"), os.path.join(self.sb.home, "src")
            archive = os.path.join(self.sb.state_dir, "archive", "t", "agy", "s")
            old = os.path.join(config, ".agent-sync-old")
            scenario.write_skill(src, "s", "new")
            scenario.write_skill(dest, "s", "old")
            unreadable = os.path.join(dest, "unreadable.md")
            with open(unreadable, "w") as f:
                f.write("x")
            os.chmod(unreadable, 0)
            self.addCleanup(lambda: [os.chmod(os.path.join(d, n), 0o644)
                                     for d, _, names in os.walk(self.sb.root) for n in names
                                     if n == "unreadable.md"])
            real = A._rename

            def cross_device(a, b):
                if b == archive:
                    raise OSError(errno.EXDEV, "Cross-device link")
                return real(a, b)

            A._rename = cross_device
            try:
                got = A.install_tree(src, dest, os.path.join(config, ".agent-sync-stage"),
                                     archive, old)
            finally:
                A._rename = real
            with open(os.path.join(dest, "SKILL.md")) as f:
                self.assertIn("new", f.read())
            self.assertIsNone(got["archived"])
            self.assertIn("could not reach the archive", got["note"])
            held = [n for n in os.listdir(old)]
            self.assertEqual(len(held), 1)
            self.assertIn(held[0], got["note"])
            self.assertTrue(os.path.lexists(os.path.join(old, held[0], "unreadable.md")))
            self.assertFalse(os.path.exists(archive), "no partial copy is left in the archive")


class Cleanup(support.SandboxCase, unittest.TestCase):
    """B7, B8, B9, SF6, SF8: the one-time cleanup and its restore."""

    def claude_flat(self, name="deploying-apps"):
        scenario.setup(self.sb, harnesses='["claude"]')
        self.assertEqual(self.sb.run().returncode, 0)
        return os.path.join(self.sb.claude_home, "skills", name)

    def test_b7_restore_with_dry_run_moves_nothing_and_keeps_the_record(self):
        flat = self.claude_flat()
        scenario.write_skill(flat, "deploying-apps")
        archived = self.sb.run("cleanup", "--yes", "deploying-apps")
        self.assertEqual(archived.returncode, 0, archived.stdout + archived.stderr)
        ts = restore_stamp(archived)
        r = self.sb.run("cleanup", "--dry-run", "--restore", ts)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("would restore", r.stdout)
        self.assertFalse(os.path.exists(flat))
        self.assertIn(ts, read_state(self.sb)["cleanup"])

    def test_b8_all_identical_compares_with_the_tree_codex_loads(self):
        scenario.setup(self.sb, harnesses='["codex"]')
        manifest = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(manifest) as f:
            text = f.read()
        self.sb.manifest(text.replace('codex     = "git"\nagy', 'codex     = "checkout"\nagy', 1))
        self.assertEqual(self.sb.run().returncode, 0)
        skill = os.path.join(self.sb.home, "src", "example-skills", "plugins", "planning",
                             "skills", "framing-ideas")
        flat = os.path.join(self.sb.home, ".agents", "skills", "framing-ideas")
        scenario.write_skill(skill, "framing-ideas", "Edited checkout")
        shutil.copytree(skill, flat)
        r = self.sb.run("cleanup", input="a\nn\nn\nn\n")
        self.assertTrue(os.path.isdir(flat), r.stdout)
        self.assertNotIn("framing-ideas", json.dumps(read_state(self.sb)["cleanup"]))

    def test_b9_a_symlink_candidate_is_listed_and_never_archived(self):
        flat = self.claude_flat()
        os.makedirs(os.path.dirname(flat))
        target = os.path.join(self.sb.home, "src", "example-skills", "plugins", "deploying",
                              "skills", "deploying-apps")
        os.symlink(os.path.relpath(target, os.path.dirname(flat)), flat)
        r = self.sb.run("cleanup", "--yes", "deploying-apps")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("a symlink is listed, never archived", r.stdout)
        self.assertTrue(os.path.islink(flat))
        self.assertEqual(read_state(self.sb)["cleanup"], {})

    def test_b9_a_restore_whose_archive_is_missing_keeps_its_record_and_fails(self):
        flat = self.claude_flat()
        scenario.write_skill(flat, "deploying-apps")
        ts = restore_stamp(self.sb.run("cleanup", "--yes", "deploying-apps"))
        shutil.rmtree(os.path.join(self.sb.state_dir, "archive", ts))
        r = self.sb.run("cleanup", "--restore", ts)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("missing from the archive", r.stdout)
        self.assertIn(ts, read_state(self.sb)["cleanup"])

    def test_sf6_cleanup_fails_when_its_inventory_could_not_be_read(self):
        self.claude_flat()
        self.sb.set("claude", "fail", {"list": "cannot reach the plugin store"})
        r = self.sb.run("cleanup", "--dry-run")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("warning:", r.stdout)

    def test_sf8_cleanup_logs_its_commands_and_shows_skills_cli_provenance(self):
        scenario.setup(self.sb, harnesses='["codex"]')
        self.assertEqual(self.sb.run().returncode, 0)
        flat = os.path.join(self.sb.home, ".agents", "skills")
        shutil.copytree(os.path.join(support.FIXTURES, "catalog-flat", "plugins", "planning",
                                     "skills", "shaping-briefs"),
                        os.path.join(flat, "shaping-briefs"))
        with open(os.path.join(self.sb.home, ".agents", ".skill-lock.json"), "w") as f:
            json.dump({"version": 3, "skills": {"shaping-briefs": {
                "source": "example-org/example-skills", "sourceType": "github"}}}, f)
        os.remove(os.path.join(self.sb.state_dir, "last-run.log"))
        r = self.sb.run("cleanup", "--yes", "shaping-briefs")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("provenance skills CLI lock entry, github source; the entry is left in "
                      "place", r.stdout)
        with open(os.path.join(self.sb.state_dir, "last-run.log")) as f:
            self.assertIn('["codex", "plugin", "marketplace", "list", "--json"]', f.read())


class Names(support.SandboxCase, unittest.TestCase):
    """B10: names compare as the destination volume compares them."""

    def setUp(self):
        super().setUp()
        with self.sb.active():
            if not A.case_insensitive(self.sb.root):
                self.skipTest("the temporary volume is case-sensitive")

    def test_b10_a_case_only_rename_with_prune_leaves_one_live_copy(self):
        one = os.path.join(self.sb.root, "one", "Review-note")
        two = os.path.join(self.sb.root, "two", "review-note")
        scenario.write_skill(one, "Review-note")
        scenario.write_skill(two, "review-note")
        loose(self.sb, ("Review-note", one))
        self.assertEqual(self.sb.run().returncode, 0)
        loose(self.sb, ("review-note", two))
        r = self.sb.run("--adopt", "review-note", "--prune", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(os.listdir(self.sb.agy_skills), ["review-note"])
        with open(os.path.join(self.sb.agy_skills, "review-note", "SKILL.md")) as f:
            self.assertIn("name: review-note", f.read())
        self.assertEqual(list(read_state(self.sb)["agy"]), ["review-note"])
        self.assertEqual(find(rows(r)[0], "agy", result="archived"), [])

    def test_b10_two_spellings_of_one_name_both_fail(self):
        one = os.path.join(self.sb.root, "one", "Review-note")
        two = os.path.join(self.sb.root, "two", "review-note")
        scenario.write_skill(one, "Review-note")
        scenario.write_skill(two, "review-note")
        loose(self.sb, ("Review-note", one), ("review-note", two))
        r = self.sb.run("--json")
        got, _ = rows(r)
        self.assertEqual([x["result"] for x in find(got, "agy")], ["failed", "failed"])
        self.assertFalse(os.path.exists(self.sb.agy_skills))


class Codex(support.SandboxCase, unittest.TestCase):
    """B11, SF3, SF5: what Codex holds is compared, not assumed."""

    def setUp(self):
        super().setUp()
        scenario.setup(self.sb, harnesses='["codex"]')

    def manifest(self, old, new):
        path = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(path) as f:
            text = f.read()
        self.assertIn(old, text)
        self.sb.manifest(text.replace(old, new, 1))

    def test_b11_a_skill_removed_upstream_leaves_the_cache_stale(self):
        self.manifest('codex     = "git"\nagy', 'codex     = "checkout"\nagy')
        self.assertEqual(self.sb.run().returncode, 0)
        os.rename(os.path.join(self.sb.home, "src", "example-skills", "plugins", "planning",
                               "skills", "framing-ideas"), os.path.join(self.sb.home, "retired"))
        r = self.sb.run("--check", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(find(rows(r)[0], "codex", "planning@example-skills")[0]["result"],
                         "stale")

    def test_sf3_dropping_the_manifest_ref_is_a_mismatch_with_the_pin_codex_keeps(self):
        self.assertEqual(self.sb.run().returncode, 0)
        self.manifest('ref       = "main"\n', "")
        self.sb.clear_calls()
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        row = find(rows(r)[0], "codex", "marketplace example-skills")[0]
        self.assertEqual(row["result"], "ref-mismatch")
        self.assertFalse([a for a in self.sb.argvs("codex") if "upgrade" in a and
                          "example-skills" in a])

    def test_sf5_a_disabled_managed_plugin_is_reported(self):
        self.assertEqual(self.sb.run().returncode, 0)
        self.sb.set("codex", "disabled", ["planning@example-skills"])
        row = find(rows(self.sb.run("--json"))[0], "codex", "planning@example-skills")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("disabled", row["detail"])

    def test_sf5_an_install_codex_does_not_list_afterwards_fails(self):
        self.sb.set("codex", "unlisted", ["planning@example-skills"])
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 1)
        row = find(rows(r)[0], "codex", "planning@example-skills")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("does not list it", row["detail"])


class Adapters(support.SandboxCase, unittest.TestCase):
    """SF2, SF4, SF6, SF7, SF8 across Claude Code and the manifest."""

    def test_sf2_a_dry_run_does_not_initialise_a_missing_harness_home(self):
        scenario.setup(self.sb, harnesses='["claude", "codex", "agy"]')
        for home in (self.sb.claude_home, self.sb.codex_home):
            shutil.rmtree(home, ignore_errors=True)
        r = self.sb.run("--dry-run", "--json")
        got, _ = rows(r)
        for h, item in (("claude", "claude CLI"), ("codex", "codex CLI"), ("agy", "agy CLI")):
            row = find(got, h, item)[0]
            self.assertEqual(row["result"], "unknown")
            self.assertIn("home not initialised", row["detail"])
        self.assertEqual(self.sb.calls("claude") + self.sb.calls("codex") +
                         self.sb.calls("agy"), [])
        for home in (self.sb.claude_home, self.sb.codex_home,
                     os.path.join(self.sb.home, ".gemini")):
            self.assertFalse(os.path.exists(home), home)

    def test_sf4_check_never_takes_its_own_fetch_as_the_applied_revision(self):
        scenario.setup(self.sb, harnesses='["claude"]')
        self.assertEqual(self.sb.run().returncode, 0)
        os.remove(os.path.join(self.sb.state_dir, "state.json"))
        scenario.move_remote(self.sb, scenario.VURL, "v2.3.0",
                             os.path.join(support.FIXTURES, "catalog-shared"), support.sha(8))
        for _ in range(2):
            r = self.sb.run("--check", "--json")
            self.assertEqual(r.returncode, 1, r.stdout)
            row = find(rows(r)[0], "claude", "marketplace example-vendor-plugins")[0]
            self.assertEqual(row["result"], "unverifiable")

    def test_sf6_a_malformed_catalog_fails_its_marketplace_and_the_run_goes_on(self):
        scenario.setup(self.sb, harnesses='["claude"]')
        catalog = os.path.join(self.sb.home, "src", "example-skills", ".claude-plugin",
                               "marketplace.json")
        with open(catalog) as f:
            doc = json.load(f)
        doc["metadata"] = {"pluginRoot": 5}         # a number where a path belongs
        doc["plugins"][0]["source"] = "plugins/planning"
        with open(catalog, "w") as f:
            json.dump(doc, f)
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        got, _ = rows(r)
        self.assertEqual(find(got, "claude", "marketplace example-skills")[0]["result"],
                         "failed")
        self.assertEqual(find(got, "claude", "editor-integration@example-vendor-plugins")[0]
                         ["result"], "installed")

    def test_sf7_option_like_names_never_reach_a_cli(self):
        scenario.setup(self.sb, harnesses='["claude"]')
        catalog = os.path.join(self.sb.home, "src", "example-skills", ".claude-plugin",
                               "marketplace.json")
        with open(catalog) as f:
            doc = json.load(f)
        doc["plugins"].append({"name": "--scope=project", "source": "./plugins/planning"})
        with open(catalog, "w") as f:
            json.dump(doc, f)
        r = self.sb.run("--json")
        row = find(rows(r)[0], "claude", "'--scope=project'@example-skills")[0]
        self.assertEqual(row["result"], "failed")
        for argv in self.sb.argvs("claude"):
            self.assertFalse(any(a.startswith("--scope=project") for a in argv), argv)

    def test_sf7_an_option_like_manifest_operand_is_a_usage_error(self):
        scenario.setup(self.sb, harnesses='["claude"]')
        path = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(path) as f:
            text = f.read()
        self.sb.manifest(text.replace('ref       = "v2.3.0"', 'ref       = "--upload-pack=x"'))
        r = self.sb.run()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.sb.calls(), [])

    def test_sf8_a_flat_copy_shadowing_a_first_install_is_reported_on_that_run(self):
        scenario.setup(self.sb, harnesses='["claude"]')
        scenario.write_skill(os.path.join(self.sb.claude_home, "skills", "deploying-apps"),
                             "deploying-apps")
        got, _ = rows(self.sb.run("--json"))
        row = find(got, "claude", "deploying-apps")[0]
        self.assertEqual(row["result"], "duplicate")
        self.assertIn("plugin deploying@example-skills (~/src/example-skills/plugins/deploying/"
                      "skills/deploying-apps)", row["detail"])

    def test_sf8_credentials_never_reach_a_dry_run_or_a_manual_fix(self):
        # Joined at run time, so the repository's address check never sees it whole.
        secret = "https://someone:hunter2" + "@example.invalid/example-vendor/other-plugins.git"
        scenario.setup(self.sb, harnesses='["claude"]')
        self.sb.remote(secret, "catalog-shared", scenario.VENDOR_TAG, ref="v2.3.0")
        path = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(path) as f:
            text = f.read()
        self.sb.manifest(text.replace('"%s"' % scenario.VURL, '"%s"' % secret))
        dry = self.sb.run("--dry-run")
        self.assertNotIn("hunter2", dry.stdout + dry.stderr)
        self.sb.manifest(text)
        self.assertEqual(self.sb.run().returncode, 0)
        self.sb.manifest(text.replace('"%s"' % scenario.VURL, '"%s"' % secret))
        r = self.sb.run()
        self.assertIn("source-mismatch", r.stdout)
        self.assertNotIn("hunter2", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
