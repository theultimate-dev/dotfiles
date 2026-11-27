"""Spec §12 Plan, Claude held and Enrolment rows, run against the fakes."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scenario  # noqa: E402
import support  # noqa: E402
from support import find, rows  # noqa: E402

HELD_SHA = "5c1e" + "a" * 60


class Plan(support.SandboxCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.checkout = scenario.setup(self.sb, harnesses='["claude", "codex"]')

    def test_missing_marketplace_is_added_and_missing_plugin_installed(self):
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        argv = self.sb.argvs("claude")
        self.assertIn(["plugin", "marketplace", "add", "--scope", "user", "--json",
                       self.checkout], argv)
        self.assertIn(["plugin", "marketplace", "add", "--scope", "user", "--json",
                       scenario.VURL + "#v2.3.0"], argv)
        self.assertIn(["plugin", "install", "--scope", "user", "--json",
                       "planning@example-skills"], argv)
        self.assertIn(["plugin", "marketplace", "add", "--json", "--ref", "main", scenario.URL],
                      self.sb.argvs("codex"))
        got, summary = rows(r)
        self.assertEqual(find(got, "claude", "reviewing@example-skills")[0]["detail"],
                         "0.2.0, enabled, user")

    def test_present_marketplaces_refresh_git_and_report_checkouts_live(self):
        self.sb.run()
        self.sb.clear_calls()
        got, _ = rows(self.sb.run("--json"))
        self.assertEqual(find(got, "claude", "marketplace example-skills")[0]["result"], "live")
        self.assertIn(["plugin", "marketplace", "update", "--json", "example-vendor-plugins"],
                      self.sb.argvs("claude"))
        self.assertIn(["plugin", "marketplace", "upgrade", "--json", "example-skills"],
                      self.sb.argvs("codex"))
        live = [a for a in self.sb.argvs("claude") if a[:2] == ["plugin", "update"]]
        self.assertEqual(live, [["plugin", "update", "--scope", "user", "--json",
                                 "editor-integration@example-vendor-plugins"]],
                         "a plugin read live from its folder is never updated")

    def test_a_new_upstream_version_is_reported_updated(self):
        self.sb.run()
        self.sb.set("claude", "update", {"editor-integration@example-vendor-plugins": "1.3.0"})
        got, _ = rows(self.sb.run("--json"))
        row = find(got, "claude", "editor-integration@example-vendor-plugins")[0]
        self.assertEqual(row["result"], "updated")
        self.assertEqual(row["detail"], "1.3.0, enabled, user (1.2.0 → 1.3.0)")

    def test_disabled_plugin_is_enabled(self):
        self.sb.run()
        self.disable("planning@example-skills")
        self.sb.clear_calls()
        got, _ = rows(self.sb.run("--json"))
        self.assertEqual(find(got, "claude", "planning@example-skills")[0]["result"], "enabled")
        self.assertIn(["plugin", "enable", "--scope", "user", "--json",
                       "planning@example-skills"], self.sb.argvs("claude"))

    def disable(self, pid):
        import json
        path = os.path.join(self.sb.claude_home, "fake-state.json")
        with open(path) as f:
            st = json.load(f)
        for p in st["plugins"]:
            if p["id"] == pid:
                p["enabled"] = False
        with open(path, "w") as f:
            json.dump(st, f)

    def test_unmanaged_plugins_are_reported_and_never_touched(self):
        import json
        self.sb.run()
        path = os.path.join(self.sb.claude_home, "fake-state.json")
        with open(path) as f:
            st = json.load(f)
        st["plugins"].append({"id": "other@example-vendor-plugins", "version": "1.0.0",
                              "scope": "user", "enabled": False})
        with open(path, "w") as f:
            json.dump(st, f)
        self.sb.clear_calls()
        r = self.sb.run("--json")
        got, _ = rows(r)
        self.assertEqual(find(got, "claude", "other@example-vendor-plugins")[0]["result"],
                         "unmanaged")
        self.assertEqual(r.returncode, 0)
        self.assertFalse(any("other@example-vendor-plugins" in a for a in
                             self.sb.argvs("claude")))
        self.assertEqual(find(got, "claude", "cc-plugin-example@builtin"), [],
                         "plugins bundled with Claude are not reported")

    def test_list_calls_get_the_one_variable_and_nothing_else_does(self):
        self.sb.run()
        for c in self.sb.calls("claude"):
            is_list = c["argv"][-2:] == ["list", "--json"]
            self.assertEqual(c["nonessential_traffic"], "1" if is_list else None, c["argv"])
        for c in self.sb.calls():
            self.assertFalse(c["stdin_tty"])

    def test_dry_run_runs_only_lists_and_writes_nothing(self):
        r = self.sb.run("--dry-run", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        for cmd in ("claude", "codex"):
            for argv in self.sb.argvs(cmd):
                self.assertIn("list", argv, argv)
        self.assertEqual([a for a in self.sb.argvs("git") if {"clone", "fetch"} & set(a)], [])
        self.assertFalse(os.path.exists(self.sb.state_dir))
        self.assertFalse(os.path.exists(self.sb.cache_home))
        got, _ = rows(r)
        install = find(got, "claude", "planning@example-skills")[0]
        self.assertEqual(install["argv"], ["claude", "plugin", "install", "--scope", "user",
                                           "--json", "planning@example-skills"])

    def test_missing_harness_is_skipped_unless_named_in_only(self):
        self.sb.remove_fake("codex")
        r = self.sb.run("--json")
        got, _ = rows(r)
        self.assertEqual(find(got, "codex", "codex CLI")[0]["result"], "skipped")
        self.assertEqual(r.returncode, 0)
        r = self.sb.run("--json", "--only", "claude,codex")
        self.assertEqual(find(rows(r)[0], "codex", "codex CLI")[0]["result"], "failed")
        self.assertEqual(r.returncode, 1)

    def test_missing_git_for_a_git_source_exits_4(self):
        self.sb.remove_fake("git")
        r = self.sb.run()
        self.assertEqual(r.returncode, 4)
        self.assertIn("git is not on PATH", r.stderr)
        self.assertEqual(self.sb.calls(), [])

    def test_source_mismatch_is_reported_never_fixed(self):
        self.sb.run()
        other = "https://example.invalid/example-org/fork.git"
        self.sb.remote(other, "catalog-shared", support.sha(9), ref="v2.3.0")
        text = open(os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")).read()
        self.sb.manifest(text.replace(scenario.VURL, other))
        self.sb.clear_calls()
        r = self.sb.run("--json")
        got, _ = rows(r)
        row = find(got, "claude", "marketplace example-vendor-plugins")[0]
        self.assertEqual(row["result"], "source-mismatch")
        self.assertIn(scenario.VURL, row["detail"])
        self.assertIn(other, row["detail"])
        self.assertEqual(find(got, "claude", "editor-integration@example-vendor-plugins")[0]
                         ["result"], "skipped")
        self.assertFalse(any(a[1:3] in (["marketplace", "add"], ["marketplace", "remove"])
                             for a in self.sb.argvs("claude")))
        self.assertEqual(r.returncode, 1)


class ClaudeHeld(support.SandboxCase, unittest.TestCase):
    PID = "editor-integration@example-vendor-plugins"

    def setUp(self):
        super().setUp()
        scenario.setup(self.sb, harnesses='["claude"]')
        self.sb.set("claude", "held", {self.PID: {"command": "npx -y editor-helper@1.2 build",
                                                  "sha256": HELD_SHA}})

    def test_declared_command_is_held_with_its_hash_and_exit_3(self):
        r = self.sb.run()
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("held         declared command awaits confirmation:", r.stdout)
        self.assertIn("`npx -y editor-helper@1.2 build`", r.stdout)
        self.assertIn("re-run with --accept-command %s=%s" % (self.PID, HELD_SHA), r.stdout)
        self.assertIn("Exit 3 (held items; nothing failed)", r.stdout)
        self.assertIn(self.PID, r.stderr, "held rows also go to stderr")
        self.assertFalse(any("-y" in a or "--yes" in a for a in self.sb.argvs("claude")))

    def test_accept_command_passes_that_hash_to_that_plugin_only(self):
        self.sb.run()
        self.sb.clear_calls()
        r = self.sb.run("--json", "--accept-command", "%s=%s" % (self.PID, HELD_SHA))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with_hash = [a for a in self.sb.argvs("claude") if "--accept-command" in a]
        self.assertEqual(with_hash, [["plugin", "install", "--scope", "user", "--json",
                                      "--accept-command", HELD_SHA, self.PID]])
        self.assertEqual(find(rows(r)[0], "claude", self.PID)[0]["result"], "installed")

    def test_a_refused_hash_stays_held_and_says_so(self):
        r = self.sb.run("--json", "--accept-command", "%s=%s" % (self.PID, "0" * 64))
        row = find(rows(r)[0], "claude", self.PID)[0]
        self.assertEqual(row["result"], "held")
        self.assertIn("the hash given was refused", row["detail"])
        self.assertEqual(row["sha256"], HELD_SHA)

    def test_accept_command_for_an_unmanaged_plugin_is_a_usage_error(self):
        r = self.sb.run("--accept-command", "x@elsewhere=%s" % HELD_SHA)
        self.assertEqual(r.returncode, 2)


class Enrolment(support.SandboxCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.checkout = scenario.setup(self.sb, harnesses='["claude", "codex"]')

    def installed(self, cmd):
        return sorted(a[-1] for a in self.sb.argvs(cmd) if a[:2] in (["plugin", "install"],
                                                                      ["plugin", "add"]))

    def test_all_enrols_every_catalog_plugin_minus_exclude(self):
        self.sb.run()
        self.assertEqual(self.installed("claude"), [
            "deploying@example-skills", "editor-integration@example-vendor-plugins",
            "planning@example-skills", "reviewing@example-skills"])
        self.assertEqual(self.installed("codex"), self.installed("claude"))

    def test_a_plugin_row_overrides_one_plugin(self):
        text = open(os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")).read()
        self.sb.manifest(text.replace('id        = "deploying@example-skills"\n'
                                      'harnesses = ["claude", "codex"]',
                                      'id        = "deploying@example-skills"\n'
                                      'harnesses = ["codex"]'))
        self.sb.run()
        self.assertNotIn("deploying@example-skills", self.installed("claude"))
        self.assertIn("deploying@example-skills", self.installed("codex"))

    def test_a_plugin_only_in_the_checkout_goes_only_where_the_checkout_is_read(self):
        scenario.add_plugin(self.checkout, "drafting", ["drafting-notes"])
        self.sb.run()
        self.assertIn("drafting@example-skills", self.installed("claude"))   # claude: checkout
        self.assertNotIn("drafting@example-skills", self.installed("codex"))  # codex: git

    def test_listed_marketplace_reports_the_rest_as_available(self):
        r = self.sb.run("--json")
        got, _ = rows(r)
        self.assertEqual([x["item"] for x in find(got, "-", result="available")],
                         ["linting@example-vendor-plugins", "formatting@example-vendor-plugins"])
        self.assertEqual(r.returncode, 0)
        r = self.sb.run("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("available", r.stdout)

    def test_a_row_naming_a_plugin_the_catalog_lacks_fails(self):
        scenario.setup(self.sb, harnesses='["claude", "codex"]',
                       extra='\n[[plugin]]\nid = "missing@example-vendor-plugins"\n')
        r = self.sb.run("--json")
        got, _ = rows(r)
        self.assertEqual({x["result"] for x in find(got, item="missing@example-vendor-plugins")},
                         {"failed"})
        self.assertEqual(find(got, "claude", "planning@example-skills")[0]["result"],
                         "installed", "everything else proceeds")
        self.assertEqual(r.returncode, 1)

    def test_dry_run_with_no_cache_gives_one_unchecked_row(self):
        got, _ = rows(self.sb.run("--dry-run", "--json"))
        codex = find(got, "codex", "marketplace example-skills")
        self.assertEqual([x["result"] for x in codex], ["unchecked"])
        self.assertEqual([x for x in find(got, "codex") if "@example-skills" in x["item"]], [])

    def test_check_fetches_into_the_own_cache_only(self):
        r = self.sb.run("--check", "--json")
        self.assertEqual(r.returncode, 1, "nothing is installed yet: drift")
        self.assertTrue(os.path.isdir(os.path.join(self.sb.cache_home, "agent-sync", "sources",
                                                   "example-skills")))
        for cmd in ("claude", "codex"):
            for argv in self.sb.argvs(cmd):
                self.assertIn("list", argv)
        self.assertEqual(sorted(os.listdir(self.sb.state_dir)), ["last-run.log", "lock"],
                         "a check records nothing: no state file, no archive")


if __name__ == "__main__":
    unittest.main()
