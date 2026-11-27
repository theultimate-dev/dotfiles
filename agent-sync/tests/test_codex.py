"""Spec §12 Codex row: stale and unverifiable caches, --repair, the ref read from config.toml."""

import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scenario  # noqa: E402
import support  # noqa: E402
from support import find, rows  # noqa: E402

PID = "planning@example-skills"


class Codex(support.SandboxCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        scenario.setup(self.sb, harnesses='["codex"]')
        r = self.sb.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # C3: Codex's first upgrade after an add refreshes every cache of the marketplace; only
        # later upgrades on an unmoved ref leave a stale cache in place.
        r = self.sb.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.cache = os.path.join(self.sb.codex_home, "plugins", "cache", "example-skills",
                                  "planning", "0.4.0")

    def tamper(self):
        with open(os.path.join(self.cache, "skills", "framing-ideas", "SKILL.md"), "a") as f:
            f.write("\nan older copy\n")

    def test_unmoved_ref_and_a_differing_cache_is_stale_and_exits_1(self):
        self.tamper()
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        got, _ = rows(r)
        self.assertEqual(find(got, "codex", "marketplace example-skills")[0]["result"],
                         "unchanged")
        row = find(got, "codex", PID)[0]
        self.assertEqual(row["result"], "stale")
        self.assertIn("cache differs from 1111111 at the same version", row["detail"])
        self.assertEqual(find(got, "codex", "reviewing@example-skills")[0]["result"], "unchanged")
        self.assertNotIn(["plugin", "add", "--json", PID], self.sb.argvs("codex")[-8:],
                         "stale is reported, not repaired, without --repair")

    def test_repair_reinstalls_only_the_stale_plugin(self):
        self.tamper()
        self.sb.clear_calls()
        r = self.sb.run("--repair", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([a for a in self.sb.argvs("codex") if a[:2] == ["plugin", "add"]],
                         [["plugin", "add", "--json", PID]])
        row = find(rows(r)[0], "codex", PID)[0]
        self.assertEqual(row["result"], "updated")
        self.assertIn("repaired", row["detail"])

    def test_repair_in_dry_run_only_plans(self):
        self.tamper()
        self.sb.clear_calls()
        got, _ = rows(self.sb.run("--repair", "--dry-run", "--json"))
        self.assertEqual(find(got, "codex", PID)[0]["argv"], ["codex", "plugin", "add", "--json",
                                                              PID])
        self.assertFalse(any(a[:2] == ["plugin", "add"] for a in self.sb.argvs("codex")))

    def test_a_moved_ref_is_upgraded(self):
        tree = scenario.move_remote(self.sb, scenario.URL, "main",
                                    os.path.join(support.FIXTURES, "catalog-flat"),
                                    support.sha(4))
        scenario.write_skill(os.path.join(tree, "plugins", "planning", "skills",
                                          "framing-ideas"), "framing-ideas", "Moved upstream.")
        got, _ = rows(self.sb.run("--json"))
        row = find(got, "codex", "marketplace example-skills")[0]
        self.assertEqual((row["result"], row["detail"]), ("updated", "main: 1111111 → 4444444"))
        self.assertEqual(find(got, "codex", PID)[0]["result"], "unchanged",
                         "the fake Codex refreshes caches when the ref moved")

    def test_unrecognised_cache_layout_is_unverifiable_and_exit_0(self):
        shutil.move(self.cache, self.cache + "-renamed")
        r = self.sb.run("--json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(find(rows(r)[0], "codex", PID)[0]["result"], "unverifiable")

    def test_ref_mismatch_is_reported_never_fixed(self):
        self.sb.remote(scenario.URL, "catalog-flat", support.sha(5), ref="release")
        path = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        text = open(path).read()
        self.sb.manifest(text.replace('ref       = "main"', 'ref       = "release"'))
        self.sb.clear_calls()
        r = self.sb.run("--json")
        got, _ = rows(r)
        row = find(got, "codex", "marketplace example-skills")[0]
        self.assertEqual(row["result"], "ref-mismatch")
        self.assertIn("Codex follows main, the manifest says release", row["detail"])
        self.assertIn("codex plugin marketplace add --json --ref release", row["detail"])
        self.assertEqual(find(got, "codex", PID)[0]["result"], "skipped")
        self.assertFalse(any(a[:3] == ["plugin", "marketplace", "remove"] or
                             a[:3] == ["plugin", "marketplace", "add"]
                             for a in self.sb.argvs("codex")))
        self.assertEqual(r.returncode, 1)

    def test_config_toml_is_read_only_and_an_unrecognised_one_is_unverifiable(self):
        cfg = os.path.join(self.sb.codex_home, "config.toml")
        with open(cfg, "w") as f:
            f.write("marketplaces = 'not a table'\n")
        before = os.stat(cfg).st_mtime_ns
        r = self.sb.run("--json")
        got, _ = rows(r)
        self.assertIn("unverifiable", [x["result"] for x in
                                       find(got, "codex", "marketplace example-skills")])
        self.assertEqual(find(got, "codex", PID)[0]["result"], "skipped",
                         "unverifiable metadata changes nothing below it")
        self.assertEqual(os.stat(cfg).st_mtime_ns, before)
        self.assertEqual(r.returncode, 0)

    def test_missing_codex_home_is_reported_as_it_stands_and_not_created(self):
        shutil.rmtree(self.sb.codex_home)
        r = self.sb.run("--json")
        row = find(rows(r)[0], "codex", "codex CLI")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("does not exist", row["detail"])
        self.assertFalse(os.path.exists(self.sb.codex_home))
        self.assertEqual(r.returncode, 1)

    def test_a_checkout_source_is_stale_until_repaired(self):
        path = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        text = open(path).read()
        self.sb.manifest(text.replace('codex     = "git"\nagy       = "checkout"',
                                      'codex     = "checkout"\nagy       = "checkout"'))
        shutil.rmtree(self.sb.codex_home)
        os.makedirs(self.sb.codex_home)
        self.sb.run()
        checkout = os.path.join(self.sb.home, "src", "example-skills")
        scenario.write_skill(os.path.join(checkout, "plugins", "planning", "skills",
                                          "framing-ideas"), "framing-ideas", "Edited locally.")
        got, _ = rows(self.sb.run("--json"))
        self.assertEqual(find(got, "codex", PID)[0]["result"], "stale")
        got, _ = rows(self.sb.run("--json", "--repair"))
        self.assertEqual(find(got, "codex", PID)[0]["result"], "updated")


if __name__ == "__main__":
    unittest.main()
