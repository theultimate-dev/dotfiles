"""Spec §12 Duplicates and Cleanup rows (spec §7, §9)."""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scenario  # noqa: E402
import support  # noqa: E402
from support import find, rows  # noqa: E402


class Machine(support.SandboxCase):
    """Synced Claude and Codex, plus flat copies in each harness's flat root."""

    def setUp(self):
        super().setUp()
        self.checkout = scenario.setup(self.sb, harnesses='["claude", "codex"]')
        r = self.sb.run()
        assert r.returncode == 0, r.stdout + r.stderr
        self.codex_flat = os.path.join(self.sb.home, ".agents", "skills")
        self.claude_flat = os.path.join(self.sb.claude_home, "skills")
        plugins = os.path.join(support.FIXTURES, "catalog-flat", "plugins")
        # identical to the plugin's copy
        self.sb.copy_fixture(os.path.join(plugins, "planning", "skills", "shaping-briefs"),
                             os.path.join(self.codex_flat, "shaping-briefs"))
        self.sb.copy_fixture(os.path.join(plugins, "deploying", "skills", "deploying-apps"),
                             os.path.join(self.claude_flat, "deploying-apps"))
        # differs: one file changed, one only in the copy
        framing = self.sb.copy_fixture(os.path.join(plugins, "planning", "skills",
                                                    "framing-ideas"),
                                       os.path.join(self.codex_flat, "framing-ideas"))
        with open(os.path.join(framing, "SKILL.md"), "a") as f:
            f.write("\nAn older local edit.\n")
        with open(os.path.join(framing, "references", "old-checklist.md"), "w") as f:
            f.write("old\n")
        # never candidates
        scenario.write_skill(os.path.join(self.codex_flat, "find-skills"), "find-skills")
        scenario.write_skill(os.path.join(self.codex_flat, "unrelated"), "unrelated")
        for name in ("shaping-briefs", "notes-a", "notes-b"):
            scenario.write_skill(os.path.join(self.codex_flat, "synced", name), name)

    def cleanup(self, *args, input=None):
        return self.sb.run("cleanup", *args, input=input)

    def stamp(self, r):
        m = re.search(r"agent-sync cleanup --restore (\S+)", r.stdout)
        return m.group(1) if m else None


class Duplicates(Machine, unittest.TestCase):
    def test_plugin_skill_and_a_flat_copy_are_duplicates_in_each_harness(self):
        r = self.sb.run("--json")
        got, _ = rows(r)
        self.assertEqual(r.returncode, 0, "duplicates are warnings")
        codex = find(got, "codex", result="duplicate")
        self.assertEqual(sorted(x["item"] for x in codex), ["framing-ideas", "shaping-briefs"])
        self.assertEqual(find(got, "codex", "shaping-briefs")[0]["detail"],
                         "plugin planning@example-skills and ~/.agents/skills/shaping-briefs; "
                         "run `agent-sync cleanup`")
        self.assertEqual([x["item"] for x in find(got, "claude", result="duplicate")],
                         ["deploying-apps"])

    def test_external_names_are_reported_as_external(self):
        got, _ = rows(self.sb.run("--json"))
        self.assertEqual(find(got, "codex", "find-skills")[0],
                         {"harness": "codex", "item": "find-skills", "result": "external",
                          "detail": "~/.agents/skills/find-skills"})
        self.assertEqual(find(got, item="unrelated"), [])

    def test_check_counts_duplicates_as_drift(self):
        self.assertEqual(self.sb.run("--check").returncode, 1)


class Cleanup(Machine, unittest.TestCase):
    def test_dry_run_lists_identical_and_differing_candidates_and_stops(self):
        r = self.cleanup("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[1/3] ~/.claude/skills/deploying-apps", r.stdout)
        self.assertIn("[2/3] ~/.agents/skills/framing-ideas", r.stdout)
        self.assertIn("[3/3] ~/.agents/skills/shaping-briefs", r.stdout)
        self.assertIn("shadows    skill framing-ideas of plugin planning@example-skills, "
                      "installed in Codex 0.4.0", r.stdout)
        self.assertIn("content    DIFFERS from the plugin: 1 file changed, 1 only in the copy "
                      "(references/old-checklist.md)", r.stdout)
        self.assertIn("content    identical to the plugin", r.stdout)
        self.assertIn("~/.agents/skills/synced/: 3 folders, not touched", r.stdout)
        self.assertNotIn("Archive this copy?", r.stdout)
        self.assertNotIn("find-skills", r.stdout.split("Not touched")[0])
        self.assertTrue(os.path.isdir(os.path.join(self.codex_flat, "shaping-briefs")))

    def test_all_remaining_identical_skips_differing(self):
        r = self.cleanup(input="a\nn\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count("Archive this copy?"), 2)
        self.assertFalse(os.path.exists(os.path.join(self.claude_flat, "deploying-apps")))
        self.assertFalse(os.path.exists(os.path.join(self.codex_flat, "shaping-briefs")))
        self.assertTrue(os.path.isdir(os.path.join(self.codex_flat, "framing-ideas")))
        stamp = self.stamp(r)
        archived = os.path.join(self.sb.state_dir, "archive", stamp, "codex", "shaping-briefs")
        self.assertTrue(os.path.isfile(os.path.join(archived, "SKILL.md")))
        with open(os.path.join(self.sb.state_dir, "state.json")) as f:
            log = json.load(f)["cleanup"][stamp]
        self.assertEqual(sorted(x["name"] for x in log), ["deploying-apps", "shaping-briefs"])
        self.assertIn("`skills list` will show archived copies as missing", r.stdout)

    def test_diff_then_quit(self):
        r = self.cleanup(input="n\nd\nq\n")
        self.assertIn("+++ ", r.stdout)
        self.assertIn("+An older local edit.", r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.codex_flat, "framing-ideas")))
        self.assertTrue(os.path.isdir(os.path.join(self.claude_flat, "deploying-apps")))

    def test_no_answer_archives_nothing(self):
        r = self.cleanup()   # stdin is /dev/null
        self.assertEqual(r.returncode, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.claude_flat, "deploying-apps")))
        self.assertIn("no answer", r.stdout)

    def test_yes_requires_names_and_archives_exactly_those(self):
        self.assertEqual(self.cleanup("--yes").returncode, 2)
        r = self.cleanup("--yes", "unrelated")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a cleanup candidate: unrelated", r.stderr)
        r = self.cleanup("--yes", "framing-ideas")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Archive this copy?", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.codex_flat, "framing-ideas")))
        self.assertTrue(os.path.isdir(os.path.join(self.codex_flat, "shaping-briefs")))

    def test_restore_round_trip(self):
        r = self.cleanup("--yes", "framing-ideas", "shaping-briefs")
        stamp = self.stamp(r)
        r = self.cleanup("--restore", stamp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.codex_flat, "framing-ideas", "SKILL.md")) as f:
            self.assertIn("An older local edit.", f.read())
        self.assertTrue(os.path.isdir(os.path.join(self.codex_flat, "shaping-briefs")))
        with open(os.path.join(self.sb.state_dir, "state.json")) as f:
            self.assertNotIn(stamp, json.load(f)["cleanup"])

    def test_restore_refuses_over_a_reappeared_name(self):
        stamp = self.stamp(self.cleanup("--yes", "framing-ideas", "shaping-briefs"))
        scenario.write_skill(os.path.join(self.codex_flat, "shaping-briefs"), "shaping-briefs",
                             "Reinstalled by something else.")
        r = self.cleanup("--restore", stamp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("~/.agents/skills/shaping-briefs exists again; not restored", r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.codex_flat, "framing-ideas")))
        archived = os.path.join(self.sb.state_dir, "archive", stamp, "codex", "shaping-briefs")
        self.assertTrue(os.path.isdir(archived), "the archived copy is kept")
        with open(os.path.join(self.sb.state_dir, "state.json")) as f:
            left = json.load(f)["cleanup"][stamp]
        self.assertEqual([x["name"] for x in left], ["shaping-briefs"])

    def test_restore_of_an_unknown_run_is_a_usage_error(self):
        self.assertEqual(self.cleanup("--restore", "1999-01-01T00-00-00").returncode, 2)

    def test_synced_is_never_offered(self):
        r = self.cleanup("--dry-run")
        self.assertNotIn("synced/shaping-briefs", r.stdout)
        self.cleanup(input="a\ny\n")
        self.assertTrue(os.path.isdir(os.path.join(self.codex_flat, "synced", "shaping-briefs")))
        self.assertTrue(os.path.isdir(os.path.join(self.codex_flat, "find-skills")))


if __name__ == "__main__":
    unittest.main()
