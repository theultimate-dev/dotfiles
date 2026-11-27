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
                                  support.cache_name("marketplace", scenario.VURL, "v2.3.0"))

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
    """B5: the swap and its record are one operation (cross-volume moves: Review3)."""

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
        self.assertIn("listed and never archived", r.stdout)
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
        # The forbidden calls and writes first, so a missing row cannot mask them.
        self.assertEqual(self.sb.calls("claude") + self.sb.calls("codex") +
                         self.sb.calls("agy"), [])
        for home in (self.sb.claude_home, self.sb.codex_home,
                     os.path.join(self.sb.home, ".gemini")):
            self.assertFalse(os.path.exists(home), home)
        got, _ = rows(r)
        for h, item in (("claude", "claude CLI"), ("codex", "codex CLI"), ("agy", "agy CLI")):
            row = find(got, h, item)[0]
            self.assertEqual(row["result"], "unknown")
            self.assertIn("home not initialised", row["detail"])

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
        for argv in self.sb.argvs("claude"):     # the forbidden call first: a row cannot mask it
            self.assertFalse(any(a.startswith("--scope=project") for a in argv), argv)
        row = find(rows(r)[0], "claude", "'--scope=project'@example-skills")[0]
        self.assertEqual(row["result"], "failed")

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


# ── Review 2 (4339b9f): every probe case, and the neighbouring variant of each ──────────────────


def captured(sb, argv, stdin=None, patches=()):
    """main() in this process -> (exit, stdout, stderr), with attributes of the script replaced
    for the duration: patches is [(name, value)]."""
    out, err = io.StringIO(), io.StringIO()
    saved = [(n, getattr(A, n)) for n, _ in patches]
    real_stdin = sys.stdin
    try:
        for n, v in patches:
            setattr(A, n, v)
        if stdin is not None:
            sys.stdin = stdin
        with sb.active(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = A.main(argv)
    finally:
        sys.stdin = real_stdin
        for n, v in saved:
            setattr(A, n, v)
    return code, out.getvalue(), err.getvalue()


def claude_flat_copy(test):
    """Claude with the example catalog installed, and a flat copy of deploying-apps shadowing
    the plugin's skill -> the flat path."""
    sb = test.sb
    scenario.setup(sb, harnesses='["claude"]')
    test.assertEqual(sb.run().returncode, 0)
    flat = os.path.join(sb.claude_home, "skills", "deploying-apps")
    shutil.copytree(os.path.join(sb.home, "src", "example-skills", "plugins", "deploying",
                                 "skills", "deploying-apps"), flat)
    return flat


def archive_flat(test, flat):
    r = test.sb.run("cleanup", "--yes", os.path.basename(flat))
    test.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    ts = restore_stamp(r)
    return ts, os.path.join(test.sb.state_dir, "archive", ts, "claude", os.path.basename(flat))


def git_market(sb, name, n):
    """A Git marketplace remote named `name`, holding the flat fixture at commit sha(n)."""
    url = "https://example.invalid/review-test/%s.git" % name
    tree = sb.remote(url, "catalog-flat", support.sha(n), ref="main")
    path = os.path.join(tree, ".claude-plugin", "marketplace.json")
    with open(path) as f:
        doc = json.load(f)
    doc["name"] = name
    with open(path, "w") as f:
        json.dump(doc, f)
    return url, tree


def agy_market(sb, name, url, extra=""):
    sb.manifest('version = 1\nharnesses = ["agy"]\n[[marketplace]]\nname = "%s"\ngit = "%s"\n'
                'ref = "main"\nharnesses = ["agy"]\n[[plugin]]\nid = "planning@%s"\n'
                'agy_skills = ["framing-ideas"]\n%s' % (name, url, name, extra))


def state_write_fails(sb):
    """atomic_write that fails with ENOSPC for the state file only."""
    real = A.atomic_write
    target = os.path.join(sb.state_dir, "state.json")

    def write(path, text):
        if path == target:
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(path, text)
    return [("atomic_write", write)]


class Review2Restore(support.SandboxCase, unittest.TestCase):
    """B1, B6: restore checks both chains at the move, and lands on the exact name."""

    def test_r2_b1_restore_refuses_a_symlink_anywhere_in_the_archive_chain(self):
        for level in ("harness", "timestamp", "archive root"):
            with self.subTest(level=level):
                self.sb.close()
                self.sb = support.Sandbox()
                flat = claude_flat_copy(self)
                ts, held = archive_flat(self, flat)
                moved = {"harness": os.path.dirname(held),
                         "timestamp": os.path.dirname(os.path.dirname(held)),
                         "archive root": os.path.join(self.sb.state_dir, "archive")}[level]
                outside = os.path.join(self.sb.home, "unrelated")
                os.rename(moved, outside)
                os.symlink(outside, moved)
                r = self.sb.run("cleanup", "--restore", ts)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("is a symlink", r.stdout)
                self.assertFalse(os.path.exists(flat))
                self.assertIn(ts, read_state(self.sb)["cleanup"])
        self.addCleanup(lambda: self.sb.close())

    def test_r2_b6_restore_lands_on_the_exact_name_or_fails(self):
        flat = claude_flat_copy(self)
        ts, held = archive_flat(self, flat)
        real = A.claim

        def appears(path):      # the name is taken between the check and the move
            if path == flat:
                scenario.write_skill(flat, "deploying-apps", "unrelated replacement")
            return real(path)

        code, out, _ = captured(self.sb, ["cleanup", "--restore", ts],
                                patches=[("claim", appears)])
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(flat + ".2"))
        with open(os.path.join(flat, "SKILL.md")) as f:
            self.assertIn("unrelated replacement", f.read())
        self.assertTrue(os.path.isdir(held))
        self.assertIn(ts, read_state(self.sb)["cleanup"])

    def test_r2_b1_a_linked_flat_root_is_the_harness_s_and_cleanup_uses_it(self):
        # Superseded by §10 "Whose symlinks": the Claude home is its CLI's to point anywhere.
        flat = claude_flat_copy(self)
        root = os.path.dirname(flat)
        os.rename(root, root + "-real")
        os.symlink(root + "-real", root)
        r = self.sb.run("cleanup", "--yes", "deploying-apps")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(root + "-real", "deploying-apps")))
        self.assertEqual(self.sb.run("cleanup", "--restore", restore_stamp(r)).returncode, 0)
        self.assertTrue(os.path.isdir(os.path.join(root + "-real", "deploying-apps")))

class Review2Names(support.SandboxCase, unittest.TestCase):
    """B2: a name agent-sync cannot record is never written, and the state is fully typed."""

    def test_r2_b2_a_catalog_skill_with_an_unusable_name_fails_and_is_not_copied(self):
        checkout = scenario.setup(self.sb, harnesses='["agy"]')
        scenario.add_plugin(checkout, "unusual", ["daily notes"])
        first = self.sb.run("--json")
        self.assertEqual(first.returncode, 1, first.stdout)
        self.assertFalse(os.path.lexists(os.path.join(self.sb.agy_skills, "daily notes")))
        row = find(rows(first)[0], "agy", "unusual/daily notes")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("not a name agent-sync can record", row["detail"])
        self.assertNotIn("daily notes", read_state(self.sb)["agy"])
        second = self.sb.run("--json")
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)

    def test_r2_b2_an_unusable_skill_name_is_never_a_cleanup_candidate(self):
        checkout = scenario.setup(self.sb, harnesses='["codex"]')
        scenario.add_plugin(checkout, "unusual", ["daily notes"])
        manifest = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(manifest) as f:
            text = f.read()
        self.sb.manifest(text.replace('codex     = "git"\nagy', 'codex     = "checkout"\nagy', 1))
        self.sb.run()
        scenario.write_skill(os.path.join(self.sb.home, ".agents", "skills", "daily notes"),
                             "daily notes")
        r = self.sb.run("cleanup", "--dry-run")
        self.assertNotIn("daily notes", r.stdout)
        self.assertEqual(self.sb.run("cleanup", "--yes", "daily notes").returncode, 2)

    def test_r2_b2_state_fields_of_the_wrong_type_are_refused(self):
        src = os.path.join(self.sb.home, "src", "review-note")
        scenario.write_skill(src, "review-note")
        loose(self.sb, ("review-note", src))
        for doc in ({"cleanup": {STAMP: [{"harness": "claude", "name": 5, "slot": 5}]}},
                    {"agy": {"review-note": {"digest": "d", "source": {"a": 1}}}},
                    {"agy": {"review-note": {"digest": "d", "path": ["x"]}}},
                    {"applied": {"claude": {"m": {"revision": 5}}}}):
            with self.subTest(doc=doc):
                write_state(self.sb, doc)
                r = self.sb.run("--prune")
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class Review2StateWrites(support.SandboxCase, unittest.TestCase):
    """B3: a state write that fails is reported with its paths, and the report still prints."""

    def setUp(self):
        super().setUp()
        self.src = os.path.join(self.sb.home, "src", "review-note")
        scenario.write_skill(self.src, "review-note", "old")
        loose(self.sb, ("review-note", self.src))
        self.assertEqual(self.sb.run().returncode, 0)

    def test_r2_b3_a_failed_state_write_after_a_copy_is_reported_and_recovers(self):
        scenario.write_skill(self.src, "review-note", "new")
        code, out, err = captured(self.sb, ["--json"], patches=state_write_fails(self.sb))
        self.assertEqual(code, 1, out + err)
        got = [json.loads(line) for line in out.splitlines()]
        self.assertEqual(got[-1]["exit"], 1, "the report is printed")
        detail = " ".join(r.get("detail", "") for r in got[:-1])
        self.assertIn("~/.local/state/agent-sync/state.json", detail)
        self.assertIn("~/.gemini/config/skills/review-note", detail)
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(find(rows(r)[0], "agy", "review-note")[0]["result"], "unchanged",
                         "a folder holding exactly what would be copied is recorded, not held")

    def test_r2_b3_a_failed_state_write_after_prune_is_reported(self):
        self.sb.manifest('version = 1\nharnesses = ["agy"]\n')
        code, out, _ = captured(self.sb, ["--prune", "--json"],
                                patches=state_write_fails(self.sb))
        self.assertEqual(code, 1, out)
        self.assertIn("state file could not be written", out)

    def test_r2_b3_a_failed_state_write_in_cleanup_and_restore_names_the_paths(self):
        self.sb.close()
        self.sb = support.Sandbox()
        self.addCleanup(self.sb.close)
        flat = claude_flat_copy(self)
        code, out, _ = captured(self.sb, ["cleanup", "--yes", "deploying-apps"],
                                patches=state_write_fails(self.sb))
        self.assertEqual(code, 1, out)
        self.assertIn("state file could not be written", out)
        self.assertIn("~/.claude/skills/deploying-apps", out)
        self.assertFalse(os.path.exists(flat))

    def test_r2_b3_the_copied_row_survives_an_interrupt_at_the_swap(self):
        scenario.write_skill(self.src, "review-note", "new")
        dest = os.path.join(self.sb.agy_skills, "review-note")
        real = A._rename

        def rename(a, b):
            real(a, b)
            if b == dest:
                os.kill(os.getpid(), signal.SIGINT)

        code, out, _ = captured(self.sb, ["--json"], patches=[("_rename", rename)])
        self.assertEqual(code, 130)
        self.assertTrue(find([json.loads(x) for x in out.splitlines()[:-1]], "agy",
                             "review-note", "copied"), out)


class Review2Prune(support.SandboxCase, unittest.TestCase):
    """B4: prune acts only on a selection it could read completely."""

    def test_r2_b4_an_identical_source_switch_moves_ownership_and_prune_keeps_it(self):
        url1, _ = git_market(self.sb, "first-market", 3)
        url2, _ = git_market(self.sb, "second-market", 4)
        agy_market(self.sb, "first-market", url1)
        self.assertEqual(self.sb.run().returncode, 0)
        agy_market(self.sb, "second-market", url2)
        self.assertEqual(self.sb.run().returncode, 0)
        self.assertEqual(read_state(self.sb)["agy"]["framing-ideas"]["source"],
                         "planning@second-market")
        del self.sb.config["remotes"][url2]
        self.sb.save_config()
        r = self.sb.run("--prune", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.sb.agy_skills, "framing-ideas")))

    def test_r2_b4_a_switch_to_a_source_that_fails_in_the_same_run_prunes_nothing(self):
        url1, _ = git_market(self.sb, "first-market", 3)
        agy_market(self.sb, "first-market", url1)
        self.assertEqual(self.sb.run().returncode, 0)
        agy_market(self.sb, "second-market", "https://example.invalid/review-test/absent.git")
        r = self.sb.run("--prune", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.sb.agy_skills, "framing-ideas")))
        self.assertIn("framing-ideas", read_state(self.sb)["agy"])

    def test_r2_b4_a_skill_folder_that_became_a_dangling_link_is_not_a_removal(self):
        checkout = scenario.setup(self.sb, harnesses='["agy"]')
        self.assertEqual(self.sb.run().returncode, 0)
        skill = os.path.join(checkout, "plugins", "planning", "skills", "framing-ideas")
        os.rename(skill, os.path.join(self.sb.home, "offline-source"))
        os.symlink(os.path.join(self.sb.home, "absent-source"), skill)
        r = self.sb.run("--prune", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.sb.agy_skills, "framing-ideas")))
        self.assertIn("holds symlinks",
                      find(rows(r)[0], "agy", "marketplace example-skills")[0]["detail"])


class Review2Sources(support.SandboxCase, unittest.TestCase):
    """B5: a marketplace and a loose skill never share a cache, a memo or a stale origin."""

    def test_r2_b5_a_loose_skill_never_reuses_a_marketplace_cache_of_the_same_key(self):
        url1, tree1 = git_market(self.sb, "skill-review-note", 3)
        url2, tree2 = git_market(self.sb, "loose-source", 4)
        for tree, body in ((tree1, "wrong repository"), (tree2, "requested repository")):
            scenario.write_skill(os.path.join(tree, "notes", "review-note"), "review-note", body)
        agy_market(self.sb, "skill-review-note", url1,
                   '[[skill]]\nname = "review-note"\ngit = "%s"\nref = "main"\n'
                   'subdir = "notes/review-note"\n' % url2)
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.sb.agy_skills, "review-note", "SKILL.md")) as f:
            self.assertIn("requested repository", f.read())
        self.assertTrue(any(url2 in a for a in self.sb.argvs("git")))

    def test_r2_b5_a_dry_run_never_reads_a_cache_cloned_from_another_url(self):
        url1, tree1 = git_market(self.sb, "first-market", 3)
        url2, _ = git_market(self.sb, "first-market-moved", 4)
        agy_market(self.sb, "first-market", url1)
        self.assertEqual(self.sb.run().returncode, 0)
        agy_market(self.sb, "first-market", url2)
        got, _ = rows(self.sb.run("--dry-run", "--json"))
        self.assertEqual(find(got, "agy", "marketplace first-market")[0]["result"], "unchecked")
        self.assertEqual(find(got, "agy", "planning/framing-ideas"), [])


class Review2Cleanup(support.SandboxCase, unittest.TestCase):
    """B6: a candidate that changed after it was shown is shown again, never archived unseen."""

    def test_r2_b6_a_copy_edited_while_the_prompt_is_open_is_not_archived(self):
        flat = claude_flat_copy(self)

        class Typing:
            def readline(self):
                scenario.write_skill(flat, "deploying-apps", "unique changes while waiting")
                return "a\n"

        code, out, _ = captured(self.sb, ["cleanup"], stdin=Typing())
        self.assertIn("changed since it was shown", out)
        self.assertTrue(os.path.isdir(flat), out)
        self.assertEqual(read_state(self.sb)["cleanup"], {})

    def test_r2_b6_a_copy_edited_before_a_yes_move_is_not_archived(self):
        flat = claude_flat_copy(self)
        real = A.ensure_dir

        def edit(path, **k):    # while agent-sync prepares the archive slot
            if path.endswith(os.path.join("claude")) and "archive" in path:
                scenario.write_skill(flat, "deploying-apps", "edited before the move")
            return real(path, **k)

        code, out, _ = captured(self.sb, ["cleanup", "--yes", "deploying-apps"],
                                patches=[("ensure_dir", edit)])
        self.assertEqual(code, 1, out)
        self.assertIn("changed since it was shown", out)
        self.assertTrue(os.path.isdir(flat))


class Review2Homes(support.SandboxCase, unittest.TestCase):
    """B8, SF1: no first command reaches a home agent-sync has not cleared."""

    def test_r2_b8_agy_is_not_called_when_its_home_is_a_symlink(self):
        for args in ([], ["--dry-run"]):
            with self.subTest(args=args):
                self.sb.close()
                self.sb = support.Sandbox()
                self.sb.manifest('version = 1\nharnesses = ["agy"]\n')
                outside = os.path.join(self.sb.home, "unrelated")
                os.makedirs(outside)
                os.symlink(outside, os.path.join(self.sb.home, ".gemini"))
                r = self.sb.run("--json", *args)
                self.assertEqual(self.sb.argvs("agy"), [])
                self.assertEqual(os.listdir(outside), [])
                self.assertIn(".gemini is a symlink", r.stdout)
        self.addCleanup(lambda: self.sb.close())

    def test_r2_sf1_an_empty_home_is_not_called_in_a_dry_run_or_check(self):
        scenario.setup(self.sb, harnesses='["claude", "codex"]')
        self.assertEqual(os.listdir(self.sb.codex_home), [])
        self.assertEqual(os.listdir(self.sb.claude_home), [])
        for mode in ("--dry-run", "--check"):
            with self.subTest(mode=mode):
                self.sb.clear_calls()
                r = self.sb.run(mode, "--json")
                self.assertEqual(self.sb.calls("codex") + self.sb.calls("claude"), [])
                got, _ = rows(r)
                for h in ("claude", "codex"):
                    self.assertIn("home not initialised", find(got, h, "%s CLI" % h)[0]["detail"])
                self.assertEqual(os.listdir(self.sb.codex_home), [])


class Review2Observations(support.SandboxCase, unittest.TestCase):
    """SF2, SF3, SF4: what a harness reports is checked, kept apart, and compared fully."""

    def test_r2_sf2_check_stays_red_after_a_held_plugin_update(self):
        scenario.setup(self.sb, harnesses='["claude"]')
        self.assertEqual(self.sb.run().returncode, 0)
        scenario.move_remote(self.sb, scenario.VURL, "v2.3.0",
                             os.path.join(support.FIXTURES, "catalog-shared"), support.sha(8))
        pid = "editor-integration@example-vendor-plugins"
        self.sb.set("claude", "held", {pid: {"command": "fixture command", "sha256": "f" * 64}})
        held = self.sb.run("--json")
        self.assertEqual(held.returncode, 3, held.stdout)
        r = self.sb.run("--check", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(find(rows(r)[0], "claude", pid)[0]["result"], "unchecked")
        accepted = self.sb.run("--accept-command", pid + "=" + "f" * 64, "--json")
        self.assertEqual(accepted.returncode, 0, accepted.stdout)
        self.assertEqual(self.sb.run("--check").returncode, 0)

    def test_r2_sf3_a_malformed_list_entry_fails_that_harness_and_the_rest_runs(self):
        scenario.setup(self.sb, harnesses='["claude", "agy"]')
        self.assertEqual(self.sb.run().returncode, 0)
        path = os.path.join(self.sb.claude_home, "fake-state.json")
        with open(path) as f:
            data = json.load(f)
        data["plugins"].append({"scope": "user", "enabled": True})
        with open(path, "w") as f:
            json.dump(data, f)
        self.sb.clear_calls()
        r = self.sb.run("--json")
        self.assertNotIn("Traceback", r.stderr)
        self.assertTrue(self.sb.argvs("agy"), "agy still runs")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(find(rows(r)[0], "claude", "claude CLI")[0]["result"], "failed")

    def test_r2_sf3_a_malformed_agy_list_fails_agy_only(self):
        scenario.setup(self.sb, harnesses='["claude", "agy"]')
        self.sb.set("agy", "plugins", [{"name": "x", "skills": "not a list"}])
        r = self.sb.run("--json")
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        got, _ = rows(r)
        self.assertEqual(find(got, "agy", "agy CLI")[0]["result"], "failed")
        self.assertTrue(find(got, "claude", "planning@example-skills"))

    def test_r2_sf4_a_skill_dropped_from_the_declaration_leaves_the_cache_stale(self):
        scenario.setup(self.sb, harnesses='["codex"]')
        manifest = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(manifest) as f:
            text = f.read()
        self.sb.manifest(text.replace('codex     = "git"\nagy', 'codex     = "checkout"\nagy', 1))
        self.assertEqual(self.sb.run().returncode, 0)
        path = os.path.join(self.sb.home, "src", "example-skills", "plugins", "reviewing",
                            ".claude-plugin", "plugin.json")
        with open(path) as f:
            doc = json.load(f)
        doc["skills"].remove("./skills/reviewing-tests")
        with open(path, "w") as f:
            json.dump(doc, f)
        r = self.sb.run("--check", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(find(rows(r)[0], "codex", "reviewing@example-skills")[0]["result"],
                         "stale")


# ── Review 3 (e7c381d): each probe case, then a test of the class rule it falls under (§10) ────


def crossing(sb):
    """A rename across the archive's boundary fails with EXDEV, as one between volumes does."""
    root = os.path.join(sb.state_dir, "archive")
    real = A._rename

    def inside(p):
        return p == root or p.startswith(root + os.sep)

    def rename(a, b):
        if inside(a) != inside(b):
            raise OSError(errno.EXDEV, "Cross-device link")
        return real(a, b)
    return [("_rename", rename)]


def files_under(root):
    return sorted(os.path.relpath(os.path.join(d, n), root)
                  for d, _, names in os.walk(root) for n in names) if os.path.isdir(root) else []


SKILL_BLOCK = '[[skill]]\nname = "review-note"\npath = "~/src/review-note"\n'


def agy_with_loose(sb):
    """The standard catalog for agy, plus a loose skill, applied once -> the checkout."""
    scenario.write_skill(os.path.join(sb.home, "src", "review-note"), "review-note")
    checkout = scenario.setup(sb, harnesses='["agy"]', extra=SKILL_BLOCK)
    r = sb.run("--json")
    assert r.returncode == 0, r.stdout + r.stderr
    return checkout


def drop_loose(sb):
    """Take the loose skill out of the manifest, so its copy is an orphan."""
    path = os.path.join(sb.config_home, "agent-sync", "manifest.toml")
    with open(path) as f:
        text = f.read()
    sb.manifest(text.replace(SKILL_BLOCK, ""))


class Review3Probes(support.SandboxCase, unittest.TestCase):
    """The nine probe-3 cases, with the expected behaviour."""

    def test_r3_b2_a_malformed_declaration_never_reads_as_a_removal(self):
        checkout = scenario.setup(self.sb, harnesses='["agy"]')
        plugin = os.path.join(checkout, "plugins", "planning")
        os.makedirs(os.path.join(plugin, "extra"))
        os.rename(os.path.join(plugin, "skills", "framing-ideas"),
                  os.path.join(plugin, "extra", "framing-ideas"))
        descriptor = os.path.join(plugin, ".claude-plugin", "plugin.json")
        with open(descriptor) as f:
            doc = json.load(f)
        doc["skills"] = ["./extra/framing-ideas", "./skills/shaping-briefs"]
        with open(descriptor, "w") as f:
            json.dump(doc, f)
        self.assertEqual(self.sb.run().returncode, 0)
        with open(descriptor, "w") as f:
            f.write('{"skills": ')
        r = self.sb.run("--prune", "--json")
        self.assertTrue(os.path.isdir(os.path.join(self.sb.agy_skills, "framing-ideas")))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(find(rows(r)[0], "agy", "prune", "skipped"), r.stdout)

    def test_r3_b2_a_dangling_default_skills_root_never_reads_as_a_removal(self):
        checkout = scenario.setup(self.sb, harnesses='["agy"]')
        self.assertEqual(self.sb.run().returncode, 0)
        base = os.path.join(checkout, "plugins", "planning", "skills")
        os.rename(base, base + "-moved")
        os.symlink(base + "-absent", base)
        r = self.sb.run("--prune", "--json")
        self.assertTrue(os.path.isdir(os.path.join(self.sb.agy_skills, "framing-ideas")))
        self.assertTrue(find(rows(r)[0], "agy", "prune", "skipped"), r.stdout)

    def test_r3_b2_a_dangling_non_skill_entry_keeps_its_siblings(self):
        checkout = scenario.setup(self.sb, harnesses='["agy"]')
        os.symlink("draft.md", os.path.join(checkout, "plugins", "planning", "skills", "notes.md"))
        r = self.sb.run("--json")
        self.assertTrue(os.path.isfile(os.path.join(self.sb.agy_skills, "framing-ideas",
                                                    "SKILL.md")), r.stdout)
        self.assertEqual(find(rows(r)[0], "agy", "planning/framing-ideas")[0]["result"],
                         "copied")

    def test_r3_b3_case_aliases_of_loose_git_skills_never_share_a_cache(self):
        url1, tree1 = git_market(self.sb, "first-market", 3)
        url2, tree2 = git_market(self.sb, "second-market", 4)
        for tree, body in ((tree1, "intended first repository"),
                           (tree2, "wrong second repository")):
            scenario.write_skill(os.path.join(tree, "notes", "Review-note"), "Review-note", body)
        self.sb.manifest('version = 1\nharnesses = ["agy"]\n'
                         '[[skill]]\nname = "Review-note"\ngit = "%s"\nref = "main"\n'
                         'subdir = "notes/Review-note"\n'
                         '[[skill]]\nname = "review-note"\ngit = "%s"\nref = "main"\n'
                         'subdir = "notes/missing"\n' % (url1, url2))
        r = self.sb.run("--json")
        installed = os.path.join(self.sb.agy_skills, "Review-note", "SKILL.md")
        self.assertTrue(os.path.isfile(installed), r.stdout)
        with open(installed) as f:
            self.assertIn("intended first repository", f.read())
        self.assertEqual(r.returncode, 1, "the second skill's subdir is missing")

    def test_r3_b4_a_nested_link_disqualifies_a_cleanup_candidate(self):
        flat = claude_flat_copy(self)
        loose_dir = os.path.join(os.path.dirname(flat), "local-references")
        os.makedirs(loose_dir)
        with open(os.path.join(loose_dir, "private-note.md"), "w") as f:
            f.write("local file")
        os.symlink(os.path.join("..", "local-references"), os.path.join(flat, "references"))
        r = self.sb.run("cleanup", input="a\n")
        self.assertTrue(os.path.isdir(flat), r.stdout)
        self.assertNotIn("identical to the plugin", r.stdout)
        self.assertEqual(files_under(os.path.join(self.sb.state_dir, "archive")), [])

    def test_r3_b1_a_cleanup_across_volumes_moves_nothing(self):
        flat = claude_flat_copy(self)
        sub = os.path.join(flat, "readonly")
        os.makedirs(sub)
        with open(os.path.join(sub, "not-removable.md"), "w") as f:
            f.write("kept in a read-only directory")
        os.chmod(sub, 0o555)
        self.addCleanup(lambda: [os.chmod(os.path.join(d, n), 0o755) for d, dirs, _ in
                                 os.walk(self.sb.root) for n in dirs if n == "readonly"])
        before = scenario.contents(flat)
        code, out, _ = captured(self.sb, ["cleanup", "--yes", "deploying-apps"],
                                patches=crossing(self.sb))
        self.assertEqual(code, 1, out)
        self.assertEqual(scenario.contents(flat), before, "the original is whole")
        self.assertEqual(files_under(os.path.join(self.sb.state_dir, "archive")), [])
        self.assertEqual(read_state(self.sb)["cleanup"], {})
        self.assertIn("XDG_STATE_HOME", out)

    def test_r3_b5_a_linked_claude_or_codex_home_is_used_as_is(self):
        for h in ("claude", "codex"):
            with self.subTest(harness=h):
                self.sb.close()
                self.sb = support.Sandbox()
                scenario.setup(self.sb, harnesses=json.dumps([h]))
                home = getattr(self.sb, h + "_home")
                other = os.path.join(self.sb.home, h + "-other-profile")
                os.rename(home, other)
                os.symlink(other, home)
                r = self.sb.run("--json")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertTrue(os.path.isfile(os.path.join(other, "fake-state.json")))
                self.assertTrue(os.path.islink(home))
                self.assertEqual(self.sb.run("--check").returncode, 0)
        self.addCleanup(lambda: self.sb.close())

    def test_r3_sf1_a_first_apply_with_a_held_update_keeps_check_red(self):
        scenario.setup(self.sb, harnesses='["claude"]')
        self.assertEqual(self.sb.run().returncode, 0)
        os.remove(os.path.join(self.sb.state_dir, "state.json"))
        scenario.move_remote(self.sb, scenario.VURL, "v2.3.0",
                             os.path.join(support.FIXTURES, "catalog-shared"), support.sha(8))
        pid = "editor-integration@example-vendor-plugins"
        self.sb.set("claude", "held", {pid: {"command": "fixture command", "sha256": "f" * 64}})
        self.assertEqual(self.sb.run().returncode, 3)
        r = self.sb.run("--check", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(find(rows(r)[0], "claude", pid)[0]["result"], "unchecked")

    def test_r3_b6_a_newly_declared_skill_the_cache_lacks_is_stale_and_repaired(self):
        checkout = scenario.setup(self.sb, harnesses='["codex"]')
        manifest = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(manifest) as f:
            text = f.read()
        self.sb.manifest(text.replace('codex     = "git"\nagy', 'codex     = "checkout"\nagy', 1))
        self.assertEqual(self.sb.run().returncode, 0)
        path = os.path.join(checkout, ".claude-plugin", "marketplace.json")
        with open(path) as f:
            catalog = json.load(f)
        entry = next(x for x in catalog["plugins"] if x["name"] == "planning")
        entry["skills"] = ["./skills/framing-ideas", "./skills/added"]
        with open(path, "w") as f:
            json.dump(catalog, f)
        scenario.write_skill(os.path.join(checkout, "plugins", "planning", "skills", "added"),
                             "added")
        pid = "planning@example-skills"
        r = self.sb.run("--json")
        self.assertEqual(find(rows(r)[0], "codex", pid)[0]["result"], "stale", r.stdout)
        self.sb.clear_calls()
        self.sb.run("--repair", "--json")
        self.assertIn(["plugin", "add", "--json", pid], self.sb.argvs("codex"))


class Review3NoCrossVolumeMoves(support.SandboxCase, unittest.TestCase):
    """Rule: every move is one rename. Across volumes the item fails with both paths, and
    nothing is copied, half-removed or detoured through another folder."""

    def assert_nothing_moved(self, out):
        self.assertIn("XDG_STATE_HOME", out)
        self.assertIn("different volume", out)
        self.assertEqual(files_under(os.path.join(self.sb.state_dir, "archive")), [])
        names = [n for d, dirs, fs in os.walk(self.sb.root) for n in dirs + fs]
        self.assertFalse([n for n in names if n.startswith((".agent-sync-old", ".agent-sync-"
                                                             "partial"))], names)

    def loose_copy(self, body="old"):
        src = os.path.join(self.sb.home, "src", "review-note")
        scenario.write_skill(src, "review-note", body)
        loose(self.sb, ("review-note", src))
        return src, os.path.join(self.sb.agy_skills, "review-note")

    def test_r3_rule_an_agy_swap_across_volumes_leaves_the_old_copy_in_place(self):
        src, dest = self.loose_copy()
        self.assertEqual(self.sb.run().returncode, 0)
        before = scenario.contents(dest)
        scenario.write_skill(src, "review-note", "new")
        code, out, _ = captured(self.sb, ["--json"], patches=crossing(self.sb))
        self.assertEqual(code, 1, out)
        self.assertEqual(scenario.contents(dest), before)
        self.assert_nothing_moved(out)
        self.assertEqual(os.listdir(self.sb.agy_skills), ["review-note"])

    def test_r3_rule_an_adopt_across_volumes_leaves_the_foreign_folder(self):
        _, dest = self.loose_copy()
        scenario.write_skill(dest, "review-note", "someone else's")
        before = scenario.contents(dest)
        code, out, _ = captured(self.sb, ["--adopt", "review-note", "--json"],
                                patches=crossing(self.sb))
        self.assertEqual(code, 1, out)
        self.assertEqual(scenario.contents(dest), before)
        self.assert_nothing_moved(out)

    def test_r3_rule_a_prune_across_volumes_keeps_the_copy_and_its_record(self):
        _, dest = self.loose_copy()
        self.assertEqual(self.sb.run().returncode, 0)
        self.sb.manifest('version = 1\nharnesses = ["agy"]\n')
        code, out, _ = captured(self.sb, ["--prune", "--json"], patches=crossing(self.sb))
        self.assertEqual(code, 1, out)
        self.assertTrue(os.path.isfile(os.path.join(dest, "SKILL.md")))
        self.assertIn("review-note", read_state(self.sb)["agy"])
        self.assert_nothing_moved(out)

    def test_r3_rule_a_restore_across_volumes_keeps_the_archive_and_its_record(self):
        flat = claude_flat_copy(self)
        ts, held = archive_flat(self, flat)
        before = scenario.contents(held)
        code, out, _ = captured(self.sb, ["cleanup", "--restore", ts],
                                patches=crossing(self.sb))
        self.assertEqual(code, 1, out)
        self.assertEqual(scenario.contents(held), before)
        self.assertFalse(os.path.exists(flat))
        self.assertIn(ts, read_state(self.sb)["cleanup"])
        self.assertIn("XDG_STATE_HOME", out)

    def test_r3_rule_the_script_has_no_copy_then_delete_path(self):
        self.assertFalse(hasattr(A, "transfer"))
        with open(support.SCRIPT) as f:
            text = f.read()
        self.assertNotIn(".agent-sync-old", text)
        self.assertNotIn("copytree(", text.replace("shutil.copytree(src, stage", ""),
                         "the only copy is into the agy stage")


class Review3CleanResolution(support.SandboxCase, unittest.TestCase):
    """Rule: --prune archives orphans only after a run that read every agy source, catalog,
    declaration and listing without error; valid siblings of a broken item still copy."""

    def breakages(self, checkout):
        planning = os.path.join(checkout, "plugins", "planning")
        manifest = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")

        def write(path, text):
            with open(path, "w") as f:
                f.write(text)

        def edit_manifest(old, new):
            with open(manifest) as f:
                text = f.read()
            self.sb.manifest(text.replace(old, new))

        return {
            "a malformed plugin.json": lambda: write(
                os.path.join(planning, ".claude-plugin", "plugin.json"), "{"),
            "a plugin.json that is not an object": lambda: write(
                os.path.join(planning, ".claude-plugin", "plugin.json"), "[]"),
            "a declared path that is missing": lambda: write(
                os.path.join(planning, ".claude-plugin", "plugin.json"),
                '{"skills": ["./skills/framing-ideas", "./skills/absent"]}'),
            "a dangling link at the catalog root": lambda: os.symlink(
                "absent.md", os.path.join(checkout, "README-link.md")),
            "a link beside the skills": lambda: os.symlink(
                "draft.md", os.path.join(planning, "skills", "notes.md")),
            "a dangling skills root": lambda: (
                os.rename(os.path.join(planning, "skills"), os.path.join(planning, "moved")),
                os.symlink("absent", os.path.join(planning, "skills"))),
            "an agy_skills name the plugin lacks": lambda: edit_manifest(
                'agy_skills = ["reviewing-code-changes"]',
                'agy_skills = ["reviewing-code-changes", "absent"]'),
            "a loose Git skill that cannot be fetched": lambda: edit_manifest(
                "[external]", '[[skill]]\nname = "far-away"\ngit = '
                '"https://example.invalid/review-test/absent.git"\n\n[external]'),
        }

    def test_r3_rule_any_resolution_error_skips_prune_and_siblings_still_copy(self):
        for name in sorted(self.breakages("x")):
            with self.subTest(breakage=name):
                self.sb.close()
                self.sb = support.Sandbox()
                checkout = agy_with_loose(self.sb)
                drop_loose(self.sb)
                self.breakages(checkout)[name]()
                r = self.sb.run("--prune", "--json")
                got, _ = rows(r)
                self.assertTrue(os.path.isfile(os.path.join(self.sb.agy_skills, "review-note",
                                                            "SKILL.md")), r.stdout)
                self.assertIn("review-note", read_state(self.sb)["agy"])
                self.assertEqual(len(find(got, "agy", "prune", "skipped")), 1, r.stdout)
                self.assertTrue(find(got, "agy", result="unchanged"), "siblings still sync")
        self.addCleanup(lambda: self.sb.close())

    def test_r3_rule_a_clean_resolution_prunes(self):
        agy_with_loose(self.sb)
        drop_loose(self.sb)
        r = self.sb.run("--prune", "--json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(find(rows(r)[0], "agy", "review-note")[0]["result"], "archived")
        self.assertFalse(os.path.exists(os.path.join(self.sb.agy_skills, "review-note")))


class Review3CacheNames(support.SandboxCase, unittest.TestCase):
    """Rule: a Git source's cache folder is named by kind, URL and ref, never by a name."""

    def test_r3_rule_cache_folders_are_named_by_the_request(self):
        url, tree = git_market(self.sb, "first-market", 3)
        scenario.write_skill(os.path.join(tree, "notes", "review-note"), "review-note")
        agy_market(self.sb, "first-market", url,
                   '[[skill]]\nname = "review-note"\ngit = "%s"\nref = "main"\n'
                   'subdir = "notes/review-note"\n' % url)
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sources = os.path.join(self.sb.cache_home, "agent-sync", "sources")
        self.assertEqual(sorted(os.listdir(sources)),
                         sorted([support.cache_name("marketplace", url, "main"),
                                 support.cache_name("skill", url, "main")]),
                         "one URL, two kinds: two folders")

    def test_r3_rule_another_ref_of_the_same_url_gets_its_own_folder(self):
        url, tree = git_market(self.sb, "first-market", 3)
        self.sb.remote(url, None, support.sha(5), ref="next", tree=tree)
        agy_market(self.sb, "first-market", url)
        self.assertEqual(self.sb.run().returncode, 0)
        self.sb.manifest(open(os.path.join(self.sb.config_home, "agent-sync", "manifest.toml"))
                         .read().replace('ref = "main"', 'ref = "next"'))
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sources = os.path.join(self.sb.cache_home, "agent-sync", "sources")
        self.assertEqual(sorted(os.listdir(sources)),
                         sorted(support.cache_name("marketplace", url, ref)
                                for ref in ("main", "next")))


class Review3CleanupLinks(support.SandboxCase, unittest.TestCase):
    """Rule: a copy that is or holds a link, at any depth, is listed and never archived; an
    unavailable digest is equal to nothing."""

    def test_r3_rule_a_link_at_any_depth_is_never_archived_by_any_answer(self):
        def at_top(flat):
            shutil.rmtree(flat)
            os.symlink(os.path.join(os.path.dirname(flat), "elsewhere"), flat)
            os.makedirs(os.path.join(os.path.dirname(flat), "elsewhere"))

        def file_link(flat):
            os.symlink("SKILL.md", os.path.join(flat, "alias.md"))

        def deep_dir_link(flat):
            os.makedirs(os.path.join(flat, "a", "b"))
            os.symlink("..", os.path.join(flat, "a", "b", "up"))

        for where, make in (("the copy itself", at_top), ("a file inside", file_link),
                            ("a folder two levels down", deep_dir_link)):
            for answer in ("y\n", "a\n", None):
                with self.subTest(where=where, answer=answer):
                    self.sb.close()
                    self.sb = support.Sandbox()
                    flat = claude_flat_copy(self)
                    make(flat)
                    r = self.sb.run("cleanup", input=answer) if answer else \
                        self.sb.run("cleanup", "--yes", "deploying-apps")
                    self.assertTrue(os.path.lexists(flat), r.stdout)
                    self.assertIn("never archived", r.stdout)
                    self.assertEqual(files_under(os.path.join(self.sb.state_dir, "archive")),
                                     [])
        self.addCleanup(lambda: self.sb.close())

    def test_r3_rule_an_unreadable_copy_is_never_identical(self):
        flat = claude_flat_copy(self)
        os.chmod(os.path.join(flat, "SKILL.md"), 0)
        self.addCleanup(os.chmod, os.path.join(flat, "SKILL.md"), 0o644)
        r = self.sb.run("cleanup", input="a\n")
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotIn("identical to the plugin", r.stdout)
        self.assertTrue(os.path.isdir(flat))


class Review3CodexInventory(support.SandboxCase, unittest.TestCase):
    """Rule: a skill the source selects and a recognised cache lacks is stale, and --repair
    reinstalls it; unverifiable is only for a layout not recognised."""

    def setUp(self):
        super().setUp()
        self.checkout = scenario.setup(self.sb, harnesses='["codex"]')
        manifest = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        with open(manifest) as f:
            text = f.read()
        self.sb.manifest(text.replace('codex     = "git"\nagy', 'codex     = "checkout"\nagy', 1))
        self.assertEqual(self.sb.run().returncode, 0)
        self.pid = "reviewing@example-skills"
        self.plugin = os.path.join(self.checkout, "plugins", "reviewing")

    def result(self):
        return find(rows(self.sb.run("--json"))[0], "codex", self.pid)[0]["result"]

    def test_r3_rule_a_skill_declared_in_plugin_json_and_missing_from_the_cache_is_stale(self):
        scenario.write_skill(os.path.join(self.plugin, "skills", "added"), "added")
        path = os.path.join(self.plugin, ".claude-plugin", "plugin.json")
        with open(path) as f:
            doc = json.load(f)
        doc["skills"].append("./skills/added")
        with open(path, "w") as f:
            json.dump(doc, f)
        self.assertEqual(self.result(), "stale")
        self.sb.clear_calls()
        self.sb.run("--repair")
        self.assertIn(["plugin", "add", "--json", self.pid], self.sb.argvs("codex"))

    def test_r3_rule_a_selected_skill_removed_from_the_cache_is_stale(self):
        version = os.path.join(self.sb.codex_home, "plugins", "cache", "example-skills",
                               "reviewing")
        cache = os.path.join(version, os.listdir(version)[0])
        shutil.rmtree(os.path.join(cache, "skills", "reviewing-tests"))
        self.assertEqual(self.result(), "stale")

    def test_r3_rule_only_an_unrecognised_layout_is_unverifiable(self):
        version = os.path.join(self.sb.codex_home, "plugins", "cache", "example-skills",
                               "reviewing")
        shutil.rmtree(version)
        self.assertEqual(self.result(), "unverifiable")


class Review3UnappliedRevision(support.SandboxCase, unittest.TestCase):
    """Rule: a plugin revision agent-sync never applied is unknown, never inherited from its
    marketplace; --check reports it unchecked until one apply succeeds for it."""

    def test_r3_rule_a_plugin_with_no_applied_revision_is_unchecked(self):
        scenario.setup(self.sb, harnesses='["claude"]')
        self.assertEqual(self.sb.run().returncode, 0)
        self.assertEqual(self.sb.run("--check").returncode, 0)
        state = read_state(self.sb)
        del state["applied"]["claude"]["example-vendor-plugins"]["plugins"]
        write_state(self.sb, state)
        r = self.sb.run("--check", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        pid = "editor-integration@example-vendor-plugins"
        self.assertEqual(find(rows(r)[0], "claude", pid)[0]["result"], "unchecked")
        self.assertEqual(self.sb.run().returncode, 0)
        self.assertEqual(self.sb.run("--check").returncode, 0)



# ── Review 4 (a556c36): each probe case, then a test of the class rule it falls under (§10) ────


@contextlib.contextmanager
def locked(*paths):
    """Each path at mode 0 for the block, as a permission-denied part of a tree leaves it."""
    modes = [(p, os.stat(p).st_mode & 0o7777) for p in paths]
    for p, _ in modes:
        os.chmod(p, 0)
    try:
        yield
    finally:
        for p, mode in modes:
            os.chmod(p, mode)


def codex_checkout(test):
    """Codex installing the example catalog from its checkout, applied once -> the checkout."""
    checkout = scenario.setup(test.sb, harnesses='["codex"]')
    edit_manifest(test.sb, 'codex     = "git"\nagy', 'codex     = "checkout"\nagy')
    test.assertEqual(test.sb.run().returncode, 0)
    return checkout


def edit_manifest(sb, old, new):
    path = os.path.join(sb.config_home, "agent-sync", "manifest.toml")
    with open(path) as f:
        text = f.read()
    assert old in text, old
    sb.manifest(text.replace(old, new, 1))


def adds_of(sb, source):
    return [a for a in sb.argvs("claude")
            if a[:3] == ["plugin", "marketplace", "add"] and a[-1].startswith(source)]


ALTERNATE_GIT = ('[[marketplace]]\nname = "vendor-alternate"\ngit = "%s"\nref = "v2.3.0"\n'
                 'claude = "git"\nharnesses = ["claude"]\nplugins = "all"\n' % scenario.VURL)
ALTERNATE_CHECKOUT = ('[[marketplace]]\nname = "skills-alternate"\ncheckout = '
                      '"~/src/example-skills"\nclaude = "checkout"\nharnesses = ["claude"]\n'
                      'plugins = "all"\n')
ROOT_ONLY = "permission bits do not bind root"


def stage_on_other_volume(sb, live):
    """_rename that fails with EXDEV only for the staged copy going live."""
    real = A._rename

    def rename(a, b):
        if b == live and ".agent-sync-stage" in a.split(os.sep):
            raise OSError(errno.EXDEV, "Cross-device link", a, None, b)
        return real(a, b)
    return [("_rename", rename)]


@unittest.skipIf(os.geteuid() == 0, ROOT_ONLY)
class Review4Probes(support.SandboxCase, unittest.TestCase):
    """The probe-4 cases, with the expected behaviour."""

    def test_r4_b1_a_second_name_for_one_fetched_catalog_fails_before_its_add(self):
        scenario.setup(self.sb, harnesses='["claude"]', extra=ALTERNATE_GIT)
        r = self.sb.run("--json")
        self.assertEqual(len(adds_of(self.sb, scenario.VURL)), 1, r.stdout)
        row = find(rows(r)[0], "claude", "marketplace vendor-alternate")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("named example-vendor-plugins, not vendor-alternate", row["detail"])
        self.assertEqual(r.returncode, 1)

    def test_r4_b2_an_unreadable_selected_skill_is_never_pruned(self):
        checkout = scenario.setup(self.sb, harnesses='["agy"]')
        self.assertEqual(self.sb.run().returncode, 0)
        with locked(os.path.join(checkout, "plugins", "planning", "skills", "framing-ideas")):
            r = self.sb.run("--prune", "--json")
        got, _ = rows(r)
        self.assertTrue(os.path.isdir(os.path.join(self.sb.agy_skills, "framing-ideas")))
        self.assertIn("framing-ideas", read_state(self.sb)["agy"])
        self.assertEqual(find(got, "agy", "planning/framing-ideas")[0]["result"], "failed")
        self.assertEqual(len(find(got, "agy", "prune", "skipped")), 1, r.stdout)
        self.assertEqual(find(got, "agy", "planning/shaping-briefs")[0]["result"], "unchanged")
        self.assertEqual(r.returncode, 1)

    def test_r4_b2_an_unreadable_loose_skill_keeps_prune_closed(self):
        retired = os.path.join(self.sb.home, "src", "retired")
        scenario.write_skill(retired, "retired")
        loose(self.sb, ("retired", retired))
        self.assertEqual(self.sb.run().returncode, 0)
        upcoming = os.path.join(self.sb.home, "src", "next-skill")
        scenario.write_skill(upcoming, "next-skill")
        loose(self.sb, ("next-skill", upcoming))
        with locked(os.path.join(upcoming, "SKILL.md")):
            r = self.sb.run("--prune", "--json")
        got, _ = rows(r)
        self.assertEqual(find(got, "agy", "next-skill")[0]["result"], "failed")
        self.assertTrue(os.path.isdir(os.path.join(self.sb.agy_skills, "retired")))
        self.assertTrue(find(got, "agy", "prune", "skipped"), r.stdout)

    def test_r4_b3_a_linked_descriptor_fails_its_plugin_before_its_selection_is_read(self):
        checkout = scenario.setup(self.sb, harnesses='["agy"]')
        edit_manifest(self.sb, 'agy_skills = ["reviewing-code-changes"]\n', "")
        descriptor = os.path.join(checkout, "plugins", "reviewing", ".claude-plugin",
                                  "plugin.json")
        with open(descriptor) as f:
            doc = json.load(f)
        doc["skills"] = ["./skills/draft-notes"]
        outside = os.path.join(self.sb.home, "other-descriptor.json")
        with open(outside, "w") as f:
            json.dump(doc, f)
        os.remove(descriptor)
        os.symlink(outside, descriptor)
        r = self.sb.run("--json")
        got, _ = rows(r)
        self.assertFalse(os.path.lexists(os.path.join(self.sb.agy_skills, "draft-notes")))
        row = find(got, "agy", "reviewing@example-skills")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("symlink", row["detail"])
        self.assertEqual(find(got, "agy", "planning/framing-ideas")[0]["result"], "copied")

    def test_r4_b4_an_unreadable_part_keeps_a_copy_from_ever_being_identical(self):
        flat = claude_flat_copy(self)
        private = os.path.join(flat, "private")
        os.mkdir(private)
        with open(os.path.join(private, "draft.md"), "w") as f:
            f.write("my customisation")
        with locked(private):
            r = self.sb.run("cleanup", input="a\n")
        self.assertTrue(os.path.isfile(os.path.join(private, "draft.md")), r.stdout)
        self.assertNotIn("identical to the plugin", r.stdout)
        self.assertIn("cannot be read in full", r.stdout)

    def test_r4_b5_restore_refuses_another_profile_and_keeps_the_archive(self):
        claude_flat_copy(self)
        home = self.sb.claude_home
        first = os.path.join(self.sb.home, "first-profile")
        second = os.path.join(self.sb.home, "second-profile")
        os.rename(home, first)
        os.symlink(first, home)
        ts, held = archive_flat(self, os.path.join(home, "skills", "deploying-apps"))
        os.remove(home)
        os.mkdir(second)
        os.symlink(second, home)
        r = self.sb.run("cleanup", "--restore", ts)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("first-profile", r.stdout)
        self.assertTrue(os.path.isdir(held))
        self.assertFalse(os.path.lexists(os.path.join(second, "skills", "deploying-apps")))
        self.assertIn(ts, read_state(self.sb)["cleanup"])
        os.remove(home)
        os.symlink(first, home)
        self.assertEqual(self.sb.run("cleanup", "--restore", ts).returncode, 0)
        self.assertTrue(os.path.isdir(os.path.join(first, "skills", "deploying-apps")))

    def test_r4_sf2_a_missing_cache_skill_is_stale_despite_an_unreadable_source_file(self):
        checkout = codex_checkout(self)
        resource = os.path.join(checkout, "plugins", "planning", "skills", "framing-ideas",
                                "private.md")
        with open(resource, "w") as f:
            f.write("source resource")
        shutil.rmtree(os.path.join(self.sb.codex_home, "plugins", "cache", "example-skills",
                                   "planning", "0.4.0", "skills", "framing-ideas"))
        with locked(resource):
            r = self.sb.run("--check", "--json")
        self.assertEqual(find(rows(r)[0], "codex", "planning@example-skills")[0]["result"],
                         "stale", r.stdout)

    def test_r4_sf3_a_stage_across_volumes_names_both_paths_and_the_rule(self):
        src = os.path.join(self.sb.home, "src", "review-note")
        live = os.path.join(self.sb.agy_skills, "review-note")
        scenario.write_skill(src, "review-note", "old body")
        loose(self.sb, ("review-note", src))
        self.assertEqual(self.sb.run().returncode, 0)
        with open(os.path.join(self.sb.state_dir, "state.json"), "rb") as f:
            before = f.read()
        scenario.write_skill(src, "review-note", "new body")
        code, out, _ = captured(self.sb, ["--json"], patches=stage_on_other_volume(self.sb, live))
        self.assertEqual(code, 1, out)
        detail = find(rows(subprocess.CompletedProcess([], 0, out))[0], "agy",
                      "review-note")[0]["detail"]
        for words in ("different volumes", "agent-sync-stage", "~/.gemini/config/skills/review-"
                      "note", "staging folder", "previous copy is restored"):
            self.assertIn(words, detail)
        with open(os.path.join(live, "SKILL.md")) as f:
            self.assertIn("old body", f.read())
        with open(os.path.join(self.sb.state_dir, "state.json"), "rb") as f:
            self.assertEqual(f.read(), before)

    def test_r4_sf1_a_linked_xdg_base_is_trusted_and_a_link_beneath_it_is_not(self):
        self.sb.manifest('version = 1\nharnesses = ["agy"]\n')
        target = os.path.join(self.sb.root, "other-state")
        alias = os.path.join(self.sb.root, "linked-state")
        os.mkdir(target)
        os.symlink(target, alias)
        env = dict(self.sb.env(), XDG_STATE_HOME=alias)
        self.sb.env = lambda: env
        self.assertEqual(self.sb.run("--json").returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(target, "agent-sync", "last-run.log")))
        elsewhere = os.path.join(self.sb.root, "elsewhere")
        os.mkdir(elsewhere)
        shutil.rmtree(os.path.join(target, "agent-sync"))
        os.symlink(elsewhere, os.path.join(target, "agent-sync"))
        self.assertNotEqual(self.sb.run("--json").returncode, 0)
        self.assertEqual(os.listdir(elsewhere), [])


@unittest.skipIf(os.geteuid() == 0, ROOT_ONLY)
class Review4ErrorIsNeverAbsence(support.SandboxCase, unittest.TestCase):
    """Rule: a filesystem error while walking, listing or reading makes the result unavailable:
    no digest from the readable part, no skill "gone", and a resolution error for prune."""

    def test_r4_rule_the_tree_readers_raise_where_a_part_cannot_be_read(self):
        tree = os.path.join(self.sb.root, "tree")
        scenario.write_skill(os.path.join(tree, "one"), "one")
        os.makedirs(os.path.join(tree, "one", "inner"))
        with open(os.path.join(tree, "one", "inner", "note.md"), "w") as f:
            f.write("x")
        with locked(os.path.join(tree, "one", "inner")):
            for reader in (A.digest_tree, A.tree_files, A.skill_dirs):
                with self.subTest(reader=reader.__name__):
                    self.assertRaises(OSError, reader, tree)
            self.assertIsNone(A.snapshot(tree))
            self.assertIn("cannot be read in full", A.blocked(tree))
            self.assertRaises(PermissionError, A.kind_of,
                              os.path.join(tree, "one", "inner", "note.md"))
        with locked(tree):
            self.assertRaises(PermissionError, A.flat_names, tree)
            self.assertRaises(PermissionError, A.case_insensitive,
                              os.path.join(tree, "not-yet", "skills"))
        self.assertIsNone(A.kind_of(os.path.join(tree, "absent")))
        self.assertEqual(A.flat_names(os.path.join(tree, "absent")), [])

    def test_r4_rule_every_unreadable_part_of_a_selection_skips_prune_and_keeps_siblings(self):
        def parts(checkout):
            planning = os.path.join(checkout, "plugins", "planning")
            docs = os.path.join(checkout, "docs")
            os.makedirs(docs, exist_ok=True)
            return {
                "a selected skill folder": os.path.join(planning, "skills", "framing-ideas"),
                "a selected SKILL.md": os.path.join(planning, "skills", "framing-ideas",
                                                    "SKILL.md"),
                "a file inside a selected skill": os.path.join(
                    planning, "skills", "framing-ideas", "templates", "note.md"),
                "a plugin's skills listing": os.path.join(planning, "skills"),
                "a plugin.json": os.path.join(planning, ".claude-plugin", "plugin.json"),
                "a folder of the catalog that holds no skill": docs,
            }
        for name in sorted(parts(self.sb.root)):
            with self.subTest(part=name):
                self.sb.close()
                self.sb = support.Sandbox()
                checkout = agy_with_loose(self.sb)
                drop_loose(self.sb)
                with locked(parts(checkout)[name]):
                    r = self.sb.run("--prune", "--json")
                got, _ = rows(r)
                self.assertTrue(os.path.isfile(os.path.join(self.sb.agy_skills, "review-note",
                                                            "SKILL.md")), r.stdout)
                self.assertIn("review-note", read_state(self.sb)["agy"])
                self.assertIn("framing-ideas", read_state(self.sb)["agy"])
                self.assertEqual(len(find(got, "agy", "prune", "skipped")), 1, r.stdout)
                self.assertEqual(find(got, "agy", "reviewing/reviewing-code-changes")[0]
                                 ["result"], "unchanged", "siblings still sync")
                self.assertEqual(r.returncode, 1)
        self.addCleanup(lambda: self.sb.close())

    def test_r4_rule_an_unreadable_codex_cache_decides_nothing(self):
        codex_checkout(self)
        cached = os.path.join(self.sb.codex_home, "plugins", "cache", "example-skills",
                              "planning", "0.4.0", "skills", "framing-ideas", "SKILL.md")
        with locked(cached):
            r = self.sb.run("--check", "--json")
        self.assertEqual(find(rows(r)[0], "codex", "planning@example-skills")[0]["result"],
                         "unverifiable", r.stdout)

    def test_r4_rule_an_unreadable_flat_root_is_a_failure_not_an_empty_folder(self):
        claude_flat_copy(self)
        with locked(os.path.join(self.sb.claude_home, "skills")):
            r = self.sb.run("--json")
            c = self.sb.run("cleanup", "--dry-run")
        self.assertEqual(find(rows(r)[0], "claude", "flat skills")[0]["result"], "failed")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(c.returncode, 1, c.stdout)
        self.assertIn("cannot be read", c.stdout)

    def test_r4_rule_no_walk_in_the_script_swallows_an_error(self):
        with open(support.SCRIPT) as f:
            text = f.read()
        walks = [line for line in text.splitlines() if "os.walk(" in line]
        self.assertTrue(walks and all("onerror=" in line for line in walks), walks)
        for probe in ("os.path.isfile(", "os.path.exists("):
            self.assertNotIn(probe, text)


class Review4DeclarationLinks(support.SandboxCase, unittest.TestCase):
    """Rule: marketplace.json, plugin.json and SKILL.md are opened only after their own chain
    passed the symlink check; a linked one fails its item before anything it says is used."""

    def test_r4_rule_a_declaration_reached_through_a_link_is_never_read(self):
        def link_in_place(path):
            os.rename(path, path + ".real")
            os.symlink(os.path.basename(path) + ".real", path)

        planning = ("plugins", "planning")
        cases = {
            "marketplace.json": ((".claude-plugin", "marketplace.json"),
                                 "marketplace example-skills", None),
            "a plugin's .claude-plugin folder": (planning + (".claude-plugin",),
                                                 "planning@example-skills",
                                                 "reviewing/reviewing-code-changes"),
            "a plugin.json": (planning + (".claude-plugin", "plugin.json"),
                              "planning@example-skills", "reviewing/reviewing-code-changes"),
            "a SKILL.md": (planning + ("skills", "framing-ideas", "SKILL.md"),
                           "planning/framing-ideas", "planning/shaping-briefs"),
        }
        for name, (rel, item, sibling) in sorted(cases.items()):
            with self.subTest(declaration=name):
                self.sb.close()
                self.sb = support.Sandbox()
                checkout = scenario.setup(self.sb, harnesses='["agy"]')
                link_in_place(os.path.join(checkout, *rel))
                r = self.sb.run("--json")
                got, _ = rows(r)
                self.assertEqual(find(got, "agy", item)[0]["result"], "failed", r.stdout)
                self.assertFalse(os.path.lexists(os.path.join(self.sb.agy_skills,
                                                              "framing-ideas")))
                if sibling:
                    self.assertEqual(find(got, "agy", sibling)[0]["result"], "copied")
        self.addCleanup(lambda: self.sb.close())


class Review4EachEntryValidated(support.SandboxCase, unittest.TestCase):
    """Rule: each manifest marketplace is checked against its catalog by itself, however its
    tree is shared with another entry, and before any harness command for it."""

    def test_r4_rule_a_shared_tree_never_lends_its_name_check(self):
        cases = {"git": (ALTERNATE_GIT, scenario.VURL, "vendor-alternate",
                         "example-vendor-plugins"),
                 "checkout": (ALTERNATE_CHECKOUT, None, "skills-alternate", "example-skills")}
        for kind, (extra, source, name, real) in sorted(cases.items()):
            with self.subTest(source=kind):
                self.sb.close()
                self.sb = support.Sandbox()
                checkout = scenario.setup(self.sb, harnesses='["claude"]', extra=extra)
                r = self.sb.run("--json")
                self.assertEqual(len(adds_of(self.sb, source or checkout)), 1, r.stdout)
                row = find(rows(r)[0], "claude", "marketplace " + name)[0]
                self.assertEqual(row["result"], "failed")
                self.assertIn("named %s, not %s" % (real, name), row["detail"])
                self.assertFalse([a for a in self.sb.argvs("claude") if name in a])
        self.addCleanup(lambda: self.sb.close())


class Review4RestoreRoot(support.SandboxCase, unittest.TestCase):
    """Rule: a cleanup record remembers the resolved flat root it came from, and restore
    refuses, keeping the archive and the record, when the current root resolves elsewhere."""

    def test_r4_rule_restore_follows_the_resolved_root_not_the_spelling(self):
        flat = claude_flat_copy(self)
        ts, held = archive_flat(self, flat)
        rec = read_state(self.sb)["cleanup"][ts][0]
        self.assertEqual(rec["root"], os.path.realpath(os.path.join(self.sb.claude_home,
                                                                    "skills")))
        other = os.path.join(self.sb.home, "other-profile")
        os.makedirs(os.path.join(other, "skills"))
        alias = os.path.join(self.sb.home, "profile-alias")
        os.symlink(self.sb.claude_home, alias)
        base = self.sb.env()
        for config_dir, code in ((other, 1), (alias, 0)):
            self.sb.env = lambda: dict(base, CLAUDE_CONFIG_DIR=config_dir)
            r = self.sb.run("cleanup", "--restore", ts)
            self.assertEqual(r.returncode, code, r.stdout)
            self.assertEqual(os.path.isdir(held), code == 1)
            self.assertEqual(ts in read_state(self.sb)["cleanup"], code == 1)
        self.assertFalse(os.path.lexists(os.path.join(other, "skills", "deploying-apps")))
        self.assertTrue(os.path.isfile(os.path.join(flat, "SKILL.md")))



# ── Review 5 (818ebcb): each probe case, then a test of the class rule it falls under (§10) ────


def bundled_alias(sb, target):
    """agy's bundled skills folder as a symlink to target."""
    alias = os.path.join(sb.home, ".gemini", "antigravity-cli", "builtin", "skills")
    os.makedirs(os.path.dirname(alias))
    os.symlink(target, alias)
    return alias


def loose_review_note(sb):
    src = os.path.join(sb.home, "src", "review-note")
    scenario.write_skill(src, "review-note", "incoming skill")
    loose(sb, ("review-note", src))
    return src


def repair_adds(test, pid):
    test.sb.clear_calls()
    test.sb.run("--repair", "--json")
    return ["plugin", "add", "--json", pid] in test.sb.argvs("codex")


@unittest.skipIf(os.geteuid() == 0, ROOT_ONLY)
class Review5Probes(support.SandboxCase, unittest.TestCase):
    """The probe-5 cases, with the expected behaviour."""

    def test_r5_b1_an_unreadable_non_skill_folder_never_triggers_a_codex_repair(self):
        checkout = codex_checkout(self)
        denied = os.path.join(checkout, "plugins", "planning", "skills", "unrelated")
        os.mkdir(denied)
        with open(os.path.join(denied, "README.md"), "w") as f:
            f.write("not a skill")
        with locked(denied):
            r = self.sb.run("--json")
            added = repair_adds(self, "planning@example-skills")
        self.assertEqual(find(rows(r)[0], "codex", "planning@example-skills")[0]["result"],
                         "unverifiable", r.stdout)
        self.assertFalse(added)

    def test_r5_b2_a_linked_bundled_skills_folder_still_blocks_a_collision(self):
        loose_review_note(self.sb)
        actual = os.path.join(self.sb.home, "bundled", "skills")
        scenario.write_skill(os.path.join(actual, "review-note"), "review-note", "bundled")
        bundled_alias(self.sb, actual)
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertFalse(os.path.lexists(os.path.join(self.sb.agy_skills, "review-note")))
        self.assertIn("bundled with agy", find(rows(r)[0], "agy", "review-note")[0]["detail"])

    def test_r5_sf1_an_unreadable_other_flat_root_never_hides_the_undo_line(self):
        flat = claude_flat_copy(self)
        other = os.path.join(self.sb.home, ".agents", "skills")
        os.makedirs(other)
        with locked(other):
            r = self.sb.run("cleanup", "--yes", os.path.basename(flat))
        self.assertNotIn("Traceback", r.stderr)
        self.assertFalse(os.path.exists(flat))
        self.assertIn("Undo: agent-sync cleanup --restore ", r.stdout)
        self.assertEqual(r.returncode, 1, "the unreadable root is still a failure")

    def test_r5_sf3_a_link_added_while_the_prompt_is_open_is_never_archived(self):
        flat = claude_flat_copy(self)
        hidden = os.path.join(flat, ".local")
        os.mkdir(hidden)
        os.mkdir(os.path.join(os.path.dirname(flat), "referenced"))

        class Answer:
            def readline(self):
                os.symlink(os.path.join("..", "..", "referenced"),
                           os.path.join(hidden, "folder"))
                return "a\n"

        code, out, _ = captured(self.sb, ["cleanup"], stdin=Answer())
        self.assertTrue(os.path.islink(os.path.join(hidden, "folder")), out)
        self.assertEqual(read_state(self.sb)["cleanup"], {})
        self.assertIn("symlink", out)


@unittest.skipIf(os.geteuid() == 0, ROOT_ONLY)
class Review5SelectionKnown(support.SandboxCase, unittest.TestCase):
    """Rule (error is never absence, at its consumers): a skill that could not be inspected is
    never a selected skill: Codex's check is unverifiable and issues no add, and no flat copy
    becomes a duplicate of it."""

    def test_r5_rule_an_uninspected_skill_makes_the_codex_check_unverifiable(self):
        cases = {"an unreadable folder in skills/": "lock",
                 "a SKILL.md that is a symlink": "link"}
        for name, how in sorted(cases.items()):
            with self.subTest(case=name):
                self.sb.close()
                self.sb = support.Sandbox()
                checkout = codex_checkout(self)
                folder = os.path.join(checkout, "plugins", "planning", "skills", "maybe")
                scenario.write_skill(folder, "maybe")
                marker = os.path.join(folder, "SKILL.md")
                with contextlib.ExitStack() as stack:
                    if how == "lock":
                        stack.enter_context(locked(folder))
                    else:
                        os.rename(marker, marker + ".real")
                        os.symlink("SKILL.md.real", marker)
                    r = self.sb.run("--check", "--json")
                    added = repair_adds(self, "planning@example-skills")
                self.assertEqual(find(rows(r)[0], "codex", "planning@example-skills")[0]
                                 ["result"], "unverifiable", r.stdout)
                self.assertFalse(added)
        self.addCleanup(lambda: self.sb.close())

    def test_r5_rule_an_uninspected_skill_is_never_a_duplicate(self):
        claude_flat_copy(self)
        checkout = os.path.join(self.sb.home, "src", "example-skills")
        folder = os.path.join(checkout, "plugins", "deploying", "skills", "maybe")
        scenario.write_skill(folder, "maybe")
        shutil.copytree(folder, os.path.join(self.sb.claude_home, "skills", "maybe"))
        self.assertTrue(find(rows(self.sb.run("--json"))[0], "claude", "maybe", "duplicate"))
        with locked(folder):
            r = self.sb.run("--json")
        self.assertFalse(find(rows(r)[0], "claude", "maybe", "duplicate"), r.stdout)
        self.assertTrue(find(rows(r)[0], "claude", "deploying-apps", "duplicate"))


@unittest.skipIf(os.geteuid() == 0, ROOT_ONLY)
class Review5HarnessPaths(support.SandboxCase, unittest.TestCase):
    """Rule: paths a harness owns and agent-sync only reads are read through links, and an
    inventory that cannot be read fails what depends on it, never "nothing there"."""

    def test_r5_rule_agy_s_bundled_skills_decide_collisions_through_a_link_or_not_at_all(self):
        for case in ("linked", "unreadable", "dangling"):
            with self.subTest(bundled=case):
                self.sb.close()
                self.sb = support.Sandbox()
                loose_review_note(self.sb)
                actual = os.path.join(self.sb.home, "bundled", "skills")
                scenario.write_skill(os.path.join(actual, "review-note"), "review-note")
                bundled_alias(self.sb, actual if case != "dangling" else actual + "-absent")
                with contextlib.ExitStack() as stack:
                    if case == "unreadable":
                        stack.enter_context(locked(actual))
                    r = self.sb.run("--json")
                copied = os.path.lexists(os.path.join(self.sb.agy_skills, "review-note"))
                self.assertEqual(copied, case == "dangling", r.stdout)
                self.assertEqual(r.returncode, 0 if case == "dangling" else 1, r.stdout)
        self.addCleanup(lambda: self.sb.close())

    def test_r5_rule_codex_s_cache_is_compared_through_its_links(self):
        codex_checkout(self)
        skill = os.path.join(self.sb.codex_home, "plugins", "cache", "example-skills",
                             "planning", "0.4.0", "skills", "framing-ideas")
        elsewhere = os.path.join(self.sb.home, "codex-elsewhere", "framing-ideas")
        os.makedirs(os.path.dirname(elsewhere))
        os.rename(skill, elsewhere)
        os.symlink(elsewhere, skill)
        r = self.sb.run("--check", "--json")
        self.assertEqual(find(rows(r)[0], "codex", "planning@example-skills")[0]["result"],
                         "unchanged", r.stdout)
        with open(os.path.join(elsewhere, "SKILL.md"), "a") as f:
            f.write("changed\n")
        r = self.sb.run("--check", "--json")
        self.assertEqual(find(rows(r)[0], "codex", "planning@example-skills")[0]["result"],
                         "stale", r.stdout)

    def test_r5_rule_the_source_plugin_json_is_still_read_only_through_a_clean_chain(self):
        checkout = codex_checkout(self)
        meta = os.path.join(checkout, "plugins", "planning", ".claude-plugin")
        os.rename(meta, meta + "-real")
        os.symlink(".claude-plugin-real", meta)
        r = self.sb.run("--check", "--json")
        self.assertNotIn(find(rows(r)[0], "codex", "planning@example-skills")[0]["result"],
                         ("unchanged", "stale"), r.stdout)
        self.assertFalse(repair_adds(self, "planning@example-skills"))


class Review5SourceRoots(support.SandboxCase, unittest.TestCase):
    """Rule: a checkout or [[skill]] path the manifest names is trusted as given, link or not;
    the link check starts beneath it."""

    def test_r5_rule_a_linked_root_is_used_and_a_link_beneath_it_is_refused(self):
        checkout = scenario.setup(self.sb, harnesses='["agy"]')
        moved = os.path.join(self.sb.home, "moved-catalog")
        os.rename(checkout, moved)
        os.symlink(moved, checkout)
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(self.sb.agy_skills, "framing-ideas",
                                                    "SKILL.md")))
        marker = os.path.join(moved, "plugins", "planning", "skills", "shaping-briefs",
                              "SKILL.md")
        os.rename(marker, marker + ".real")
        os.symlink("SKILL.md.real", marker)
        r = self.sb.run("--json")
        self.assertEqual(find(rows(r)[0], "agy", "planning/shaping-briefs")[0]["result"],
                         "failed", r.stdout)


if __name__ == "__main__":
    unittest.main()
