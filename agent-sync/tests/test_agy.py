"""Spec §12 agy copy and Resolution rows: copies into ~/.gemini/config/skills/, ownership,
both catalog layouts, declared skills paths, front matter, name collisions, agy_skills."""

import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scenario  # noqa: E402
import support  # noqa: E402
from support import find, rows  # noqa: E402

FRAMING = "planning/framing-ideas"


class AgyCopy(support.SandboxCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.checkout = scenario.setup(self.sb, harnesses='["agy"]')
        self.skills = self.sb.agy_skills
        self.state = os.path.join(self.sb.state_dir, "state.json")

    def run_json(self, *args):
        r = self.sb.run("--json", *args)
        return r, rows(r)[0]

    def source(self, *parts):
        return os.path.join(self.checkout, "plugins", *parts)

    def test_first_copy(self):
        r, got = self.run_json()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(x["item"] for x in find(got, "agy", result="copied")),
                         [FRAMING, "planning/shaping-briefs", "reviewing/reviewing-code-changes"])
        self.assertEqual(find(got, "agy", FRAMING)[0]["detail"], "3333333 (clean), 4 files")
        self.assertEqual(sorted(os.listdir(self.skills)), ["framing-ideas", "reviewing-code-changes",
                                                           "shaping-briefs"])
        with open(self.state) as f:
            record = json.load(f)["agy"]["framing-ideas"]
        self.assertEqual(record["source"], "planning@example-skills")
        self.assertEqual(record["revision"], "3333333 (clean)")
        self.assertFalse(os.path.exists(os.path.join(self.sb.home, ".gemini", "config",
                                                     ".agent-sync-stage")))

    def test_the_report_ends_with_the_reload_hint_after_an_agy_change(self):
        r = self.sb.run()
        self.assertIn("run /skills reload in agy", r.stdout)
        self.assertNotIn("run /skills reload in agy", self.sb.run().stdout)

    def test_second_run_is_unchanged_and_writes_nothing(self):
        self.sb.run()
        before = scenario.mtimes(os.path.join(self.sb.home, ".gemini"))
        state_before = os.stat(self.state).st_mtime_ns
        r, got = self.run_json()
        self.assertEqual({x["result"] for x in find(got, "agy")}, {"unchanged"})
        self.assertEqual(scenario.mtimes(os.path.join(self.sb.home, ".gemini")), before)
        self.assertEqual(os.stat(self.state).st_mtime_ns, state_before)
        self.assertFalse(os.path.exists(os.path.join(self.sb.state_dir, "archive")))

    def test_source_change_archives_the_old_copy(self):
        self.sb.run()
        scenario.write_skill(self.source("planning", "skills", "framing-ideas"), "framing-ideas",
                             "Changed in the checkout.")
        self.sb.set_checkout(self.checkout, support.sha(3), dirty=True)
        r, got = self.run_json()
        row = find(got, "agy", FRAMING)[0]
        self.assertEqual(row["result"], "copied")
        self.assertIn("3333333 (dirty)", row["detail"])
        self.assertIn("previous copy archived to ~/.local/state/agent-sync/archive/",
                      row["detail"])
        with open(os.path.join(self.skills, "framing-ideas", "SKILL.md")) as f:
            self.assertIn("Changed in the checkout.", f.read())
        archived = os.path.join(self.sb.state_dir, "archive")
        (stamp,) = os.listdir(archived)
        with open(os.path.join(archived, stamp, "agy", "framing-ideas", "SKILL.md")) as f:
            self.assertIn("Fixture skill.", f.read())

    def test_symlink_in_a_source_fails_that_skill_only(self):
        os.symlink("/etc/hosts", self.source("planning", "skills", "shaping-briefs", "hosts"))
        r, got = self.run_json()
        row = find(got, "agy", "planning/shaping-briefs")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("symlink in source: hosts", row["detail"])
        self.assertEqual(find(got, "agy", FRAMING)[0]["result"], "copied")
        self.assertFalse(os.path.exists(os.path.join(self.skills, "shaping-briefs")))
        self.assertEqual(r.returncode, 1)

    def test_foreign_folder_is_held_and_adopt_archives_it_first(self):
        scenario.write_skill(os.path.join(self.skills, "framing-ideas"), "framing-ideas",
                             "Hand-made.")
        r, got = self.run_json()
        row = find(got, "agy", FRAMING)[0]
        self.assertEqual((row["result"], row["reason"]), ("held", "foreign"))
        self.assertEqual(row["detail"], "~/.gemini/config/skills/framing-ideas exists and is not "
                                        "agent-sync's; --adopt framing-ideas")
        self.assertEqual(r.returncode, 3)
        r, got = self.run_json("--adopt", "framing-ideas")
        self.assertEqual(find(got, "agy", FRAMING)[0]["result"], "copied")
        archived = os.path.join(self.sb.state_dir, "archive")
        (stamp,) = os.listdir(archived)
        with open(os.path.join(archived, stamp, "agy", "framing-ideas", "SKILL.md")) as f:
            self.assertIn("Hand-made.", f.read())

    def test_hand_edited_owned_folder_is_held(self):
        self.sb.run()
        with open(os.path.join(self.skills, "framing-ideas", "SKILL.md"), "a") as f:
            f.write("\nmy own note\n")
        scenario.write_skill(self.source("planning", "skills", "framing-ideas"), "framing-ideas",
                             "Changed upstream.")
        r, got = self.run_json()
        row = find(got, "agy", FRAMING)[0]
        self.assertEqual((row["result"], row["reason"]), ("held", "edited"))
        with open(os.path.join(self.skills, "framing-ideas", "SKILL.md")) as f:
            self.assertIn("my own note", f.read())
        r, got = self.run_json("--adopt", "framing-ideas")
        self.assertEqual(find(got, "agy", FRAMING)[0]["result"], "copied")

    def test_destination_parent_that_is_a_symlink_is_refused(self):
        real = os.path.join(self.sb.root, "elsewhere")
        os.makedirs(real)
        os.makedirs(os.path.join(self.sb.home, ".gemini"))
        os.symlink(real, os.path.join(self.sb.home, ".gemini", "config"))
        r, got = self.run_json()
        self.assertEqual([(x["item"], x["result"]) for x in find(got, "agy")],
                         [("skills folder", "failed")])
        self.assertEqual(os.listdir(real), [])
        self.assertEqual(r.returncode, 1)

    def test_a_skill_that_left_the_manifest_is_orphaned_and_prune_archives_it(self):
        self.sb.run()
        path = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        text = open(path).read()
        self.sb.manifest(text.replace('exclude   = ["experiments"]',
                                      'exclude   = ["experiments", "planning"]'))
        r, got = self.run_json()
        self.assertEqual(sorted(x["item"] for x in find(got, "agy", result="orphaned")),
                         ["framing-ideas", "shaping-briefs"])
        self.assertTrue(os.path.isdir(os.path.join(self.skills, "framing-ideas")))
        self.assertEqual(r.returncode, 0)
        r, got = self.run_json("--prune")
        self.assertEqual(len(find(got, "agy", result="archived")), 2)
        self.assertFalse(os.path.exists(os.path.join(self.skills, "framing-ideas")))
        with open(self.state) as f:
            self.assertNotIn("framing-ideas", json.load(f)["agy"])

    def test_a_loose_path_skill_is_copied(self):
        loose = self.sb.copy_fixture("loose", os.path.join(self.sb.home, "src", "my-skills"))
        scenario.setup(self.sb, harnesses='["agy"]', extra='\n[[skill]]\nname = '
                                                           '"my-local-skill"\npath = '
                                                           '"~/src/my-skills/my-local-skill"\n')
        r, got = self.run_json()
        row = find(got, "agy", "my-local-skill")[0]
        self.assertEqual(row["result"], "copied")
        self.assertIn("local folder, digest", row["detail"])
        self.assertTrue(os.path.isfile(os.path.join(self.skills, "my-local-skill", "SKILL.md")))
        self.assertTrue(os.path.isdir(loose))

    def test_a_loose_git_skill_is_copied_from_its_own_cache(self):
        url = "https://example.invalid/example-org/standalone-skills.git"
        self.sb.remote(url, "standalone-skills", support.sha(6), ref="v1.0.0")
        scenario.setup(self.sb, harnesses='["agy"]', extra=(
            '\n[[skill]]\nname = "writing-release-notes"\ngit = "%s"\nref = "v1.0.0"\n'
            'subdir = "skills/writing-release-notes"\n' % url))
        r, got = self.run_json()
        row = find(got, "agy", "writing-release-notes")[0]
        self.assertEqual((row["result"], row["detail"]), ("copied", "6666666, 1 file"))
        cache = os.path.join(self.sb.cache_home, "agent-sync", "sources",
                             "+skill-writing-release-notes")
        self.assertIn(["-c", "core.symlinks=false", "clone", "--no-checkout", "--", url, cache],
                      self.sb.argvs("git"))


class Resolution(support.SandboxCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.checkout = scenario.setup(self.sb, harnesses='["agy"]', vendor_agy="git",
                                       vendor_harnesses='["claude", "codex", "agy"]')

    def run_json(self, *args):
        r = self.sb.run("--json", *args)
        return r, rows(r)[0]

    def test_both_layouts_and_declared_skills_paths(self):
        r, got = self.run_json()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        items = sorted(x["item"] for x in find(got, "agy", result="copied"))
        self.assertEqual(items, ["editor-integration/editor-setup",   # shared root, entry paths
                                 "planning/framing-ideas", "planning/shaping-briefs",
                                 "reviewing/reviewing-code-changes"])
        self.assertEqual(find(got, "agy", "editor-integration/editor-setup")[0]["detail"],
                         "2222222, 1 file")

    def test_plugin_json_skills_paths_leave_undeclared_folders_out(self):
        path = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        text = open(path).read()
        self.sb.manifest(text.replace('agy_skills = ["reviewing-code-changes"]\n', ""))
        r, got = self.run_json()
        reviewing = sorted(x["item"] for x in find(got, "agy") if x["item"].startswith("review"))
        self.assertEqual(reviewing, ["reviewing/reviewing-code-changes",
                                     "reviewing/reviewing-tests"])

    def test_a_skills_path_that_is_a_folder_of_skills(self):
        scenario.setup(self.sb, harnesses='["agy"]', vendor_agy="git",
                       vendor_harnesses='["claude", "codex", "agy"]',
                       extra='\n[[plugin]]\nid = "linting@example-vendor-plugins"\n')
        r, got = self.run_json()
        self.assertEqual(sorted(x["item"] for x in find(got, "agy") if "linting" in x["item"]),
                         ["linting/lint-config", "linting/lint-rules"])

    def test_name_and_front_matter_mismatch_fails(self):
        scenario.write_skill(os.path.join(self.checkout, "plugins", "planning", "skills",
                                          "shaping-briefs"), "shaping-briefs",
                             front_name="shaping-brief")
        r, got = self.run_json()
        row = find(got, "agy", "planning/shaping-briefs")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("front matter says name: shaping-brief", row["detail"])
        self.assertEqual(r.returncode, 1)

    def collide(self):
        scenario.add_plugin(self.checkout, "drafting", ["framing-ideas"])
        scenario.write_skill(os.path.join(self.checkout, "plugins", "drafting", "skills",
                                          "framing-ideas"), "framing-ideas", "A different one.")

    def test_two_skills_of_the_same_name_both_fail_and_the_rest_proceeds(self):
        self.sb.run()
        before = scenario.mtimes(os.path.join(self.sb.agy_skills, "framing-ideas"))
        self.collide()
        r, got = self.run_json()
        failed = find(got, "agy", result="failed")
        self.assertEqual(sorted(x["item"] for x in failed),
                         ["drafting/framing-ideas", "planning/framing-ideas"])
        for x in failed:
            self.assertEqual(x["reason"], "name collision")
        self.assertIn("name collision with drafting/framing-ideas",
                      find(got, "agy", "planning/framing-ideas")[0]["detail"])
        self.assertEqual(scenario.mtimes(os.path.join(self.sb.agy_skills, "framing-ideas")),
                         before, "the owned copy under that name is untouched")
        self.assertEqual(find(got, "agy", "planning/shaping-briefs")[0]["result"], "unchanged")
        self.assertEqual(r.returncode, 1)

    def test_a_collision_does_not_stop_the_other_harnesses(self):
        scenario.setup(self.sb, harnesses='["claude", "codex", "agy"]', vendor_agy="git",
                       vendor_harnesses='["claude", "codex", "agy"]')
        self.collide()
        r, got = self.run_json()
        self.assertEqual(find(got, "claude", "planning@example-skills")[0]["result"], "installed")
        self.assertEqual(find(got, "codex", "planning@example-skills")[0]["result"], "installed")
        self.assertEqual(r.returncode, 1)

    def test_collision_with_a_bundled_agy_skill(self):
        builtin = os.path.join(self.sb.home, ".gemini", "antigravity-cli", "builtin", "skills")
        scenario.write_skill(os.path.join(builtin, "shaping-briefs"), "shaping-briefs")
        r, got = self.run_json()
        row = find(got, "agy", "planning/shaping-briefs")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("a skill bundled with agy", row["detail"])
        self.assertEqual(find(got, "agy", "planning/framing-ideas")[0]["result"], "copied")

    def test_collision_with_an_installed_agy_plugin(self):
        self.sb.set("agy", "plugins", [{"name": "alpha", "enabled": True, "version": "0.1.0",
                                        "path": "/x", "skills": ["framing-ideas"]}])
        r, got = self.run_json()
        self.assertIn("agy plugin alpha", find(got, "agy", "planning/framing-ideas")[0]["detail"])

    def test_unknown_agy_skills_name_fails_that_plugins_agy_rows(self):
        path = os.path.join(self.sb.config_home, "agent-sync", "manifest.toml")
        text = open(path).read()
        self.sb.manifest(text.replace('agy_skills = ["reviewing-code-changes"]',
                                      'agy_skills = ["reviewing-code-changes", "nope"]'))
        r, got = self.run_json()
        row = find(got, "agy", "reviewing@example-skills")[0]
        self.assertEqual(row["result"], "failed")
        self.assertIn("agy_skills names nope", row["detail"])
        self.assertEqual([x for x in find(got, "agy") if x["item"].startswith("reviewing/")], [])
        self.assertEqual(find(got, "agy", "planning/framing-ideas")[0]["result"], "copied")


if __name__ == "__main__":
    unittest.main()
