"""C6: `agy plugin install <dir>` twice, with a changed skill between: does the second pick it up?

Recorded for a later version (spec §5.3); v1 does not install agy plugins. The test runs only
after showing that agy keeps its state inside the temp HOME (its real list is empty too, so an
empty list alone proves nothing). It asserts its own setup; the behaviour goes to the results.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness as h  # noqa: E402


class AgyPluginInstallTwice(h.ContractCase):
    TEST_ID = "C6"
    NEEDS = ("agy", "git")

    def installed(self, step):
        listed = self.ok(step, ["agy", "plugin", "list", "--json"]).json()
        return {p["name"]: p for p in listed}

    def test_record_second_install_after_a_change(self):
        self.prove_isolated("agy")
        catalog = self.iso.make_catalog()
        source = os.path.join(catalog, "plugins", "alpha")

        self.ok("first install", ["agy", "plugin", "install", source])
        first = self.installed("list after first install")
        self.assertIn("alpha", first)
        dest = first["alpha"]["path"]
        dest_skills = os.path.join(dest, "skills")
        src_skills = os.path.join(source, "skills")
        inode = os.stat(dest).st_ino
        h.record(self.iso, self.TEST_ID, "first install", entry=first["alpha"],
                 installed_tree=sorted(h.snapshot(dest)),
                 skills_match_source=h.tree_digest(dest_skills) == h.tree_digest(src_skills))

        h.write_skill(source, "alpha-skill", "Changed between the two installs.")
        h.write_skill(source, "alpha-added", "Added between the two installs.")
        second = self.run_cli("second install", ["agy", "plugin", "install", source])
        after = self.installed("list after second install")
        h.record(self.iso, self.TEST_ID, "second install",
                 returncode=second.returncode, entry=after.get("alpha"),
                 skills_match_source=(os.path.isdir(dest_skills) and
                                      h.tree_digest(dest_skills) == h.tree_digest(src_skills)),
                 directory_replaced=os.path.exists(dest) and os.stat(dest).st_ino != inode,
                 installed_tree=sorted(h.snapshot(dest)))

        manifest = os.path.join(self.iso.home, ".gemini", "config", "import_manifest.json")
        if os.path.exists(manifest):
            with open(manifest) as f:
                h.record(self.iso, self.TEST_ID, "import_manifest.json", content=f.read())


if __name__ == "__main__":
    unittest.main()
