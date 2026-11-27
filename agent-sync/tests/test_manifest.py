"""Spec §12, Manifest and Hygiene rows: parsing and every validation rule of spec §3."""

import os
import re
import sys
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

A = support.load_script()

BASE = """
version = 1
[[marketplace]]
name = "example-skills"
git = "example-org/example-skills"
harnesses = ["claude", "codex"]
"""


def parse(text):
    return A.parse_manifest(textwrap.dedent(text), "/manifest.toml")


class ExampleManifest(unittest.TestCase):
    def test_example_parses(self):
        with open(support.EXAMPLE) as f:
            m = parse(f.read())
        self.assertEqual(list(m.marketplaces), ["example-skills", "example-vendor-plugins"])
        skills = m.marketplaces["example-skills"]
        self.assertEqual(skills.plugins, "all")
        self.assertEqual(skills.exclude, ("experiments",))
        self.assertEqual(skills.source, {"claude": "checkout", "codex": "git", "agy": "checkout"})
        self.assertEqual(m.plugins["reviewing@example-skills"].harnesses,
                         ("claude", "codex", "agy"))
        self.assertEqual(m.plugins["reviewing@example-skills"].agy_skills,
                         ("reviewing-code-changes",))
        self.assertEqual(m.plugins["deploying@example-skills"].harnesses, ("claude", "codex"))
        self.assertEqual(m.plugins["editor-integration@example-vendor-plugins"].harnesses,
                         ("claude", "codex"))
        self.assertEqual([s.name for s in m.skills], ["writing-release-notes", "my-local-skill"])
        self.assertEqual(m.external, frozenset({"find-skills"}))

    def test_example_paths_expand_against_home(self):
        sb = support.Sandbox()
        self.addCleanup(sb.close)
        with sb.active(), open(support.EXAMPLE) as f:
            m = parse(f.read())
        self.assertEqual(m.marketplaces["example-skills"].checkout,
                         os.path.join(sb.home, "src", "example-skills"))
        self.assertEqual(m.skills[1].path, os.path.join(sb.home, "src", "my-skills",
                                                        "my-local-skill"))


class Validation(unittest.TestCase):
    def assertRejected(self, text, message):
        with self.assertRaises(A.UsageError) as cm:
            parse(text)
        self.assertIn(message, str(cm.exception))

    def test_minimal_manifest_parses(self):
        m = parse(BASE)
        self.assertEqual(m.harnesses, ("claude", "codex", "agy"))

    def test_version_must_be_1(self):
        self.assertRejected(BASE.replace("version = 1", "version = 2"), "version must be 1")
        self.assertRejected(BASE.replace("version = 1", ""), "version must be 1")

    def test_not_toml(self):
        self.assertRejected("version = ", "not valid TOML")

    def test_unknown_top_level_key(self):
        self.assertRejected(BASE + "\nharness = ['claude']\n", "unknown key 'harness'")

    def test_unknown_table_keys(self):
        self.assertRejected(BASE.replace('harnesses = ["claude", "codex"]',
                                         'harnesses = ["claude"]\nrefs = "main"'),
                            "marketplace example-skills: unknown key 'refs'")
        self.assertRejected(BASE + '[[plugin]]\nid = "a@example-skills"\nharness = ["claude"]\n',
                            "plugin a@example-skills: unknown key 'harness'")
        self.assertRejected(BASE + '[[skill]]\nname = "s"\npath = "/x"\nsubdirs = "y"\n',
                            "skill s: unknown key 'subdirs'")
        self.assertRejected(BASE + '[external]\nskill = ["x"]\n', "external: unknown key 'skill'")

    def test_unknown_harness_and_source(self):
        self.assertRejected(BASE.replace('["claude", "codex"]', '["claude", "gemini"]'),
                            "unknown harness 'gemini'")
        self.assertRejected(BASE + 'claude = "pull"\n', "claude must be one of")

    def test_plugin_must_name_a_declared_marketplace(self):
        self.assertRejected(BASE + '[[plugin]]\nid = "a@elsewhere"\n',
                            "marketplace 'elsewhere' is not declared")
        self.assertRejected(BASE + '[[plugin]]\nid = "no-marketplace"\n',
                            "id must be plugin@marketplace")

    def test_plugin_harnesses_fall_back_to_the_marketplace(self):
        m = parse(BASE + '[[plugin]]\nid = "a@example-skills"\n'
                         '[[plugin]]\nid = "b@example-skills"\nharnesses = ["codex"]\n')
        self.assertEqual(m.plugins["a@example-skills"].harnesses, ("claude", "codex"))
        self.assertEqual(m.plugins["b@example-skills"].harnesses, ("codex",))

    def test_plugin_with_no_harnesses_anywhere(self):
        text = BASE.replace('harnesses = ["claude", "codex"]\n', "")
        self.assertRejected(text + '[[plugin]]\nid = "a@example-skills"\n',
                            "no harnesses, and marketplace example-skills gives no default")

    def test_plugin_listed_twice(self):
        row = '[[plugin]]\nid = "a@example-skills"\n'
        self.assertRejected(BASE + row + row, "listed twice")

    def test_harness_with_source_none(self):
        self.assertRejected(BASE + 'codex = "none"\n', "harnesses names codex, whose source is "
                                                       "none")
        text = BASE + 'agy = "none"\n[[plugin]]\nid = "a@example-skills"\nharnesses = ["agy"]\n'
        self.assertRejected(text, 'goes to agy, but marketplace example-skills has agy = "none"')

    def test_source_needs_its_location(self):
        text = BASE.replace('git = "example-org/example-skills"\n', 'checkout = "/src/x"\n')
        self.assertRejected(text, 'claude uses "git" (the default) but no git is given')
        self.assertRejected(BASE + 'codex = "checkout"\n', 'codex = "checkout" requires checkout')

    def test_unused_harness_needs_no_source(self):
        text = BASE.replace('git = "example-org/example-skills"\n',
                            'checkout = "/src/x"\nclaude = "checkout"\ncodex = "checkout"\n')
        parse(text)  # agy is not used by this marketplace, so its default "git" is not needed

    def test_git_value_format(self):
        self.assertRejected(BASE.replace("example-org/example-skills", "not a url"),
                            "is not owner/repo or an https/ssh Git URL")
        for good in ("example-org/example-skills", "https://example.invalid/a/b.git",
                     "ssh://example.invalid/a/b.git", "git@localhost:a/b.git"):
            parse(BASE.replace("example-org/example-skills", good))

    def test_ref_needs_git(self):
        text = BASE.replace('git = "example-org/example-skills"\n',
                            'checkout = "/src/x"\nref = "main"\nclaude = "checkout"\n'
                            'codex = "checkout"\n')
        self.assertRejected(text, "ref needs git")

    def test_plugins_all_requires_harnesses(self):
        text = BASE.replace('harnesses = ["claude", "codex"]\n', 'plugins = "all"\n')
        self.assertRejected(text, 'plugins = "all" requires harnesses')
        self.assertRejected(BASE + 'plugins = "some"\n', 'plugins must be "listed" or "all"')

    def test_exclude_requires_all(self):
        self.assertRejected(BASE + 'exclude = ["x"]\n', 'exclude requires plugins = "all"')

    def test_excluded_and_listed(self):
        text = BASE + 'plugins = "all"\nexclude = ["a"]\n[[plugin]]\nid = "a@example-skills"\n'
        self.assertRejected(text, "is both excluded by marketplace example-skills and listed")

    def test_agy_skills_without_agy(self):
        text = BASE + '[[plugin]]\nid = "a@example-skills"\nagy_skills = ["x"]\n'
        self.assertRejected(text, "agy_skills given, but its harnesses omit agy")

    def test_skill_sources(self):
        self.assertRejected(BASE + '[[skill]]\nname = "s"\n', "give exactly one of git or path")
        self.assertRejected(BASE + '[[skill]]\nname = "s"\npath = "/x"\ngit = "a/b"\n',
                            "give exactly one of git or path")
        self.assertRejected(BASE + '[[skill]]\nname = "s"\npath = "/x"\nref = "v1"\n',
                            "ref and subdir go with git, not path")
        self.assertRejected(BASE + '[[skill]]\nname = "s"\ngit = "a/b"\nsubdir = "../x"\n',
                            "subdir must be a path inside the repository")

    def test_two_skills_share_a_name(self):
        skill = '[[skill]]\nname = "s"\npath = "/x"\n'
        self.assertRejected(BASE + skill + skill, "two [[skill]] entries share this name")

    def test_relative_paths_rejected(self):
        self.assertRejected(BASE + '[[skill]]\nname = "s"\npath = "src/s"\n',
                            "is a relative path")
        self.assertRejected(BASE + 'checkout = "./x"\n', "is a relative path")

    def test_tilde_expansion(self):
        sb = support.Sandbox()
        self.addCleanup(sb.close)
        with sb.active():
            m = parse(BASE + 'checkout = "~/src/example-skills"\n'
                             '[[skill]]\nname = "s"\npath = "~/src/s"\n')
        self.assertEqual(m.marketplaces["example-skills"].checkout,
                         os.path.join(sb.home, "src", "example-skills"))
        self.assertEqual(m.skills[0].path, os.path.join(sb.home, "src", "s"))

    def test_all_problems_are_reported_together(self):
        with self.assertRaises(A.UsageError) as cm:
            parse(BASE + 'exclude = ["x"]\nbogus = 1\n')
        self.assertEqual(len(str(cm.exception).splitlines()), 2)


class FromTheCommandLine(support.SandboxCase, unittest.TestCase):
    def test_invalid_manifest_exits_2_and_runs_nothing(self):
        self.sb.manifest(BASE + "typo = true\n")
        r = self.sb.run("--dry-run")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("unknown key 'typo'", r.stderr)
        self.assertEqual(self.sb.calls(), [])

    def test_missing_manifest_exits_2(self):
        r = self.sb.run()
        self.assertEqual(r.returncode, 2)
        self.assertIn("no manifest at ~/.config/agent-sync/manifest.toml", r.stderr)

    def test_manifest_flag_overrides_the_location(self):
        path = os.path.join(self.sb.root, "other.toml")
        with open(path, "w") as f:
            f.write(BASE + "typo = true\n")
        r = self.sb.run("--manifest", path)
        self.assertEqual(r.returncode, 2)
        self.assertIn("other.toml", r.stderr)

    def test_missing_checkout_is_an_error_only_where_it_is_used(self):
        with open(support.EXAMPLE) as f:
            self.sb.manifest(f.read())
        r = self.sb.run("--dry-run")  # claude and agy read ~/src/example-skills
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("checkout ~/src/example-skills does not exist or cannot be read (used by claude)", r.stderr)
        self.assertIn("skill my-local-skill: path ~/src/my-skills/my-local-skill does not exist",
                      r.stderr)
        self.assertEqual(self.sb.calls(), [])
        r = self.sb.run("--dry-run", "--only", "codex")  # codex follows git; no path needed
        self.assertNotEqual(r.returncode, 2, r.stderr)

    def test_usage_errors_exit_2(self):
        for args in (["--only", "gemini"], ["--accept-command", "a@b=nothex"],
                     ["--dry-run", "--check"], ["cleanup", "--yes"]):
            r = self.sb.run(*args)
            self.assertEqual(r.returncode, 2, args)


class Hygiene(unittest.TestCase):
    """The two AGENTS.md greps, applied to the example manifest and every fixture."""

    HOME_PATH = re.compile(r"/User[s]/")
    EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    def files(self):
        yield support.EXAMPLE
        for top in (support.FIXTURES, support.FAKES):
            for root, _, names in os.walk(top):
                for n in names:
                    if not n.endswith(".pyc"):
                        yield os.path.join(root, n)

    def test_no_home_paths_or_addresses(self):
        for path in self.files():
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIsNone(self.HOME_PATH.search(text), path)
            self.assertIsNone(self.EMAIL.search(text), path)

    def test_example_names_only_placeholders(self):
        with open(support.EXAMPLE) as f:
            text = f.read()
        gits = re.findall(r'^git\s*=\s*"([^"]*)"', text, re.M)
        owners = {re.sub(r"^https://[^/]+/", "", g).split("/")[0] for g in gits}
        self.assertLessEqual(owners, {"example-org", "example-vendor"})
        for path in re.findall(r'"(~/[^"]*)"', text):
            self.assertTrue(path.startswith("~/src/"), path)


if __name__ == "__main__":
    unittest.main()
