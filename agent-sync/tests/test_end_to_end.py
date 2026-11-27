"""Plan step 5: end-to-end runs against the fakes, one per harness combination, and the sample
report of spec §8 reproduced from fixtures, so the documented output is a test, not a promise."""

import itertools
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scenario  # noqa: E402
import support  # noqa: E402
from support import rows  # noqa: E402

# Spec §8, verbatim. The spec is not tracked, so the sample is kept here.
SAMPLE = """\
agent-sync 0.1.0 · manifest ~/.config/agent-sync/manifest.toml

HARNESS  ITEM                                   RESULT       DETAIL
claude   marketplace example-skills             live         checkout 3f2a91c (clean), digest unchanged
claude   marketplace example-vendor-plugins     updated      v2.3.0: 8e01d4a → 8e01d4a (catalog refreshed)
claude   planning@example-skills                unchanged    0.4.0, enabled, user
claude   reviewing@example-skills               installed    0.2.0, enabled, user
claude   editor-integration@example-vendor-…    held         declared command awaits confirmation:
                                                               `npx -y editor-helper@1.2 build`
                                                               re-run with --accept-command editor-integration@example-vendor-plugins=5c1e…
codex    marketplace example-skills             updated      main: 77b0c2e → 9d14a6f
codex    planning@example-skills                unchanged    0.4.0, cache digest matches 9d14a6f
codex    reviewing@example-skills               stale        cache differs from 9d14a6f at the same version; see "Codex stale cache" in docs/agent-sync.md
codex    find-skills                            external     ~/.agents/skills/find-skills
-        linting@example-vendor-plugins         available    in the catalog, not in the manifest
codex    shaping-briefs                         duplicate    plugin planning@example-skills and ~/.agents/skills/shaping-briefs; run `agent-sync cleanup`
agy      planning/framing-ideas                 copied       3f2a91c (clean), 4 files
agy      reviewing/reviewing-code-changes       unchanged    3f2a91c
agy      my-local-skill                         held         ~/.gemini/config/skills/my-local-skill exists and is not agent-sync's; --adopt my-local-skill

Summary: 3 changed · 4 unchanged · 1 live · 2 held · 1 stale · 1 duplicate · 0 failed
Next:    restart Claude Code sessions or run /reload-plugins · restart Codex sessions ·
         run /skills reload in agy
Exit 3 (held items; nothing failed)
"""

HELD_SHA = "5c1e" + "0" * 60

# Where the implementation departs from the sample, each deliberately:
DEVIATIONS = [
    # A refresh that leaves the revision where it was is not a change: the sample's own summary
    # counts this row as unchanged (4 unchanged, 3 changed), and a second run must read 0 changed.
    ("claude   marketplace example-vendor-plugins     updated      "
     "v2.3.0: 8e01d4a → 8e01d4a (catalog refreshed)",
     "claude   marketplace example-vendor-plugins     unchanged    "
     "v2.3.0: 8e01d4a (catalog refreshed)"),
    # The hash is printed whole, so the re-run line can be copied as it stands.
    ("=5c1e…", "=" + HELD_SHA),
    # Spec §10's table wins over the sample: a stale cache exits 1 even when items are held.
    ("Exit 3 (held items; nothing failed)", "Exit 1 (stale items)"),
]

CHECKOUT = "3f2a91c" + "0" * 33
VENDOR = "8e01d4a" + "0" * 33
MAIN_BEFORE = "77b0c2e" + "0" * 33
MAIN_AFTER = "9d14a6f" + "0" * 33

MANIFEST = """\
version = 1

[[marketplace]]
name      = "example-skills"
git       = "{url}"
ref       = "main"
checkout  = "~/src/example-skills"
claude    = "checkout"
codex     = "git"
agy       = "checkout"
harnesses = ["claude", "codex", "agy"]
plugins   = "all"
exclude   = ["deploying", "experiments"]

[[marketplace]]
name      = "example-vendor-plugins"
git       = "{vurl}"
ref       = "v2.3.0"
codex     = "none"
agy       = "none"
harnesses = ["claude"]

[[plugin]]
id = "planning@example-skills"
{planning}

[[plugin]]
id = "reviewing@example-skills"
{reviewing}
agy_skills = ["reviewing-code-changes"]

[[plugin]]
id = "editor-integration@example-vendor-plugins"

[[skill]]
name = "my-local-skill"
path = "~/src/my-skills/my-local-skill"

[external]
skills = ["find-skills"]
"""


class SampleReport(support.SandboxCase, unittest.TestCase):
    def manifest(self, planning, reviewing):
        self.sb.manifest(MANIFEST.format(url=scenario.URL, vurl=scenario.VURL,
                                         planning=planning, reviewing=reviewing))

    def test_the_spec_sample_report_reproduced_from_fixtures(self):
        sb = self.sb
        sb.remote(scenario.URL, "catalog-flat", MAIN_BEFORE, ref="main")
        vendor = sb.remote(scenario.VURL, "catalog-shared", VENDOR, ref="v2.3.0")
        catalog = os.path.join(vendor, ".claude-plugin", "marketplace.json")
        with open(catalog) as f:
            doc = json.load(f)
        doc["plugins"] = [p for p in doc["plugins"] if p["name"] != "formatting"]
        with open(catalog, "w") as f:
            json.dump(doc, f)
        sb.checkout("catalog-flat", "src/example-skills", head=CHECKOUT)
        sb.copy_fixture("loose", os.path.join(sb.home, "src", "my-skills"))
        scenario.write_skill(os.path.join(sb.agy_skills, "my-local-skill"), "my-local-skill",
                             "Made by hand before agent-sync.")
        sb.set("claude", "held", {"editor-integration@example-vendor-plugins": {
            "command": "npx -y editor-helper@1.2 build", "sha256": HELD_SHA}})

        # The run before: planning not yet in agy, reviewing not yet in Claude.
        self.manifest('harnesses = ["claude", "codex"]', 'harnesses = ["codex", "agy"]')
        first = sb.run()
        self.assertEqual(first.returncode, 3, first.stdout + first.stderr)

        # Between the runs: main moves upstream; Codex's upgrade leaves reviewing's cache
        # behind (the unmoved-cache skip of C3); two flat copies appear in ~/.agents/skills.
        scenario.move_remote(sb, scenario.URL, "main",
                             os.path.join(support.FIXTURES, "catalog-flat"), MAIN_AFTER)
        sb.set("codex", "upgrade_skips", ["reviewing@example-skills"])
        cache = os.path.join(sb.codex_home, "plugins", "cache", "example-skills", "reviewing",
                             "0.2.0", "skills", "reviewing-code-changes", "SKILL.md")
        with open(cache, "a") as f:
            f.write("\nan older copy\n")
        flat = os.path.join(sb.home, ".agents", "skills")
        scenario.write_skill(os.path.join(flat, "find-skills"), "find-skills")
        shutil.copytree(os.path.join(support.FIXTURES, "catalog-flat", "plugins", "planning",
                                     "skills", "shaping-briefs"),
                        os.path.join(flat, "shaping-briefs"))
        self.manifest('agy_skills = ["framing-ideas"]', "")

        r = sb.run()
        expected = SAMPLE
        for old, new in DEVIATIONS:
            self.assertIn(old, expected)
            expected = expected.replace(old, new)
        self.assertEqual(r.stdout, expected)
        self.assertEqual(r.returncode, 1)


class Combinations(unittest.TestCase):
    """Dry run, run, run again: the second run changes nothing and writes nothing."""

    def check(self, combo):
        sb = support.Sandbox()
        self.addCleanup(sb.close)
        scenario.setup(sb, harnesses=json.dumps(list(combo)))
        dry = sb.run("--dry-run", "--json")
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertFalse(os.path.exists(sb.state_dir))
        self.assertFalse(os.path.exists(os.path.join(sb.home, ".gemini")))
        first = sb.run("--json")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        _, summary = rows(first)
        self.assertGreater(summary["summary"]["changed"], 0)
        for h in combo:
            self.assertTrue(any(x["harness"] == h for x in rows(first)[0]), h)
        state = os.path.join(sb.state_dir, "state.json")
        stamp = os.stat(state).st_mtime_ns if os.path.exists(state) else None
        gemini = scenario.mtimes(os.path.join(sb.home, ".gemini"))
        second = sb.run("--json")
        got, summary = rows(second)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(summary["summary"]["changed"], 0, second.stdout)
        self.assertEqual(os.stat(state).st_mtime_ns if os.path.exists(state) else None, stamp)
        self.assertEqual(scenario.mtimes(os.path.join(sb.home, ".gemini")), gemini)
        check = sb.run("--check")
        self.assertEqual(check.returncode, 0, check.stdout)

    def test_every_combination_of_harnesses(self):
        harnesses = ("claude", "codex", "agy")
        for n in (1, 2, 3):
            for combo in itertools.combinations(harnesses, n):
                with self.subTest(combo=combo):
                    self.check(combo)


class Interrupted(support.SandboxCase, unittest.TestCase):
    def test_ctrl_c_writes_the_state_so_far_prints_a_partial_report_and_exits_130(self):
        import contextlib
        import io
        A = support.load_script()
        scenario.setup(self.sb, harnesses='["agy"]')
        steps = list(A.SYNC_STEPS)
        real_copy = A.agy_copy
        copied = []

        def copy_then_interrupt(ctx, skill, label):
            row = real_copy(ctx, skill, label)
            copied.append(skill.name)
            if len(copied) == 2:
                raise KeyboardInterrupt
            return row

        A.agy_copy = copy_then_interrupt
        self.addCleanup(setattr, A, "agy_copy", real_copy)
        self.addCleanup(A.SYNC_STEPS.__setitem__, slice(None), steps)
        out = io.StringIO()
        with self.sb.active(), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            code = A.main([])
        self.assertEqual(code, 130)
        self.assertIn("Exit 130 (interrupted; the report above is partial)", out.getvalue())
        with open(os.path.join(self.sb.state_dir, "state.json")) as f:
            self.assertEqual(sorted(json.load(f)["agy"]), sorted(copied))
        self.assertTrue(os.path.isfile(os.path.join(self.sb.state_dir, "last-run.log")))
        r = self.sb.run("--json")
        got, summary = rows(r)
        self.assertEqual(summary["summary"]["changed"], 1, "the re-run repeats only the rest")


if __name__ == "__main__":
    unittest.main()
