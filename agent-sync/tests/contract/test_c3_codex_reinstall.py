"""C3: does `codex plugin add` on an installed plugin, same version, changed bytes, reinstall in place?

Pass condition (spec §12): the cache digest after the add equals the source's; nothing is removed
if the add fails (simulated by making the catalog unreadable). This decides whether agent-sync
gets a `--repair` for `stale` rows (spec §5.2).

The stale state is made the way it arises: the cache holds different bytes from the source at the
same version, and `marketplace upgrade` with an unmoved ref does not fix it. Along the way the test
records when `upgrade` refreshes the cache, which the spec's `stale` detection depends on.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness as h  # noqa: E402

PLUGIN = "alpha@%s" % h.MARKETPLACE


def tamper(cache):
    with open(os.path.join(cache, "skills", "alpha-skill", "SKILL.md"), "a") as f:
        f.write("\nA stale line the source does not have.\n")
    with open(os.path.join(cache, "skills", "alpha-skill", "stale-only.md"), "w") as f:
        f.write("Only in the cache.\n")


class CodexReinstall(h.ContractCase):
    TEST_ID = "C3"
    NEEDS = ("codex", "git")

    def cache_dir(self):
        return os.path.join(self.iso.codex_home, "plugins", "cache", h.MARKETPLACE, "alpha",
                            "0.1.0")

    def upgrade(self, step):
        r = self.ok(step, ["codex", "plugin", "marketplace", "upgrade", "--json", h.MARKETPLACE])
        return r.json().get("upgradedRoots", [])

    def test_git_source_add_reinstalls_in_place(self):
        self.prove_isolated("codex")
        catalog = self.iso.make_catalog()
        source = os.path.join(catalog, "plugins", "alpha")
        self.ok("marketplace add (git)",
                ["codex", "plugin", "marketplace", "add", "--json", "--ref", "main",
                 self.git_url_for(catalog)])
        added = self.ok("plugin add", ["codex", "plugin", "add", "--json", PLUGIN]).json()
        cache = self.cache_dir()
        self.assertEqual(os.path.realpath(added["installedPath"]), os.path.realpath(cache),
                         "cache layout is not plugins/cache/<marketplace>/<plugin>/<version>/")
        self.assertEqual(h.tree_digest(cache), h.tree_digest(source))

        # Which upgrades refresh the cache when the ref has not moved?
        refreshes = []
        for i in range(3):
            tamper(cache)
            roots = self.upgrade("unmoved upgrade %d" % (i + 1))
            refreshes.append({"upgrade": i + 1, "upgradedRoots": len(roots),
                              "cache_matches_source": h.tree_digest(cache) == h.tree_digest(source)})
        h.record(self.iso, self.TEST_ID, "unmoved-ref upgrades on a tampered cache",
                 refreshes=refreshes)

        # And a moved ref, same version, changed bytes.
        h.write_skill(source, "alpha-skill", "Changed at the same version.")
        self.iso.commit_all(catalog, "same version, changed bytes")
        roots = self.upgrade("moved-ref upgrade")
        h.record(self.iso, self.TEST_ID, "moved-ref upgrade", upgradedRoots=len(roots),
                 cache_matches_source=h.tree_digest(cache) == h.tree_digest(source))

        # The repair candidate: a stale cache, an unmoved ref, then `plugin add` again.
        tamper(cache)
        self.upgrade("unmoved upgrade before repair")
        stale = h.tree_digest(cache) != h.tree_digest(source)
        inode_before = os.stat(cache).st_ino
        self.ok("plugin add on the installed plugin", ["codex", "plugin", "add", "--json", PLUGIN])
        repaired = h.tree_digest(cache) == h.tree_digest(source)
        h.record(self.iso, self.TEST_ID, "repair by plugin add",
                 stale_before=stale, cache_matches_source_after=repaired,
                 cache_only_file_left=os.path.exists(
                     os.path.join(cache, "skills", "alpha-skill", "stale-only.md")),
                 directory_replaced=os.stat(cache).st_ino != inode_before,
                 versions_in_cache=sorted(os.listdir(os.path.dirname(cache))))
        self.assertTrue(stale, "could not produce a stale cache to repair")
        self.assertTrue(repaired, "`codex plugin add` did not reinstall the cache in place")

        # A failing add must leave the installed cache as it was.
        tamper(cache)
        before = h.snapshot(cache)
        snapshot_catalog = os.path.join(self.iso.codex_home, ".tmp", "marketplaces",
                                        h.MARKETPLACE, ".claude-plugin", "marketplace.json")
        catalog_file = snapshot_catalog if os.path.exists(snapshot_catalog) else None
        h.record(self.iso, self.TEST_ID, "catalog made unreadable",
                 path=catalog_file or "(snapshot catalog not found)")
        self.assertIsNotNone(catalog_file, "Codex's marketplace snapshot is not where expected")
        os.chmod(catalog_file, 0)
        try:
            failed = self.run_cli("plugin add with an unreadable catalog",
                                  ["codex", "plugin", "add", "--json", PLUGIN])
        finally:
            os.chmod(catalog_file, 0o644)
        survived = h.snapshot(cache) == before
        h.record(self.iso, self.TEST_ID, "failed add", returncode=failed.returncode,
                 cache_unchanged=survived)
        self.assertNotEqual(failed.returncode, 0, "add succeeded with an unreadable catalog")
        self.assertTrue(survived, "a failed add removed or changed the installed cache")

    def test_local_checkout_source_add_picks_up_working_tree(self):
        self.prove_isolated("codex")
        checkout = self.iso.make_catalog()
        source = os.path.join(checkout, "plugins", "alpha")
        self.ok("marketplace add (local path)",
                ["codex", "plugin", "marketplace", "add", "--json", checkout])
        listed = self.ok("marketplace list", ["codex", "plugin", "marketplace", "list",
                                              "--json"]).json()
        self.ok("plugin add", ["codex", "plugin", "add", "--json", PLUGIN])
        cache = self.cache_dir()

        h.write_skill(source, "alpha-skill", "Uncommitted edit in the checkout.")
        stale = h.tree_digest(cache) != h.tree_digest(source)
        self.ok("plugin add after a checkout edit", ["codex", "plugin", "add", "--json", PLUGIN])
        repaired = h.tree_digest(cache) == h.tree_digest(source)
        h.record(self.iso, self.TEST_ID, "local checkout source",
                 marketplace_root=[m.get("root") for m in listed["marketplaces"]],
                 stale_after_edit=stale, cache_matches_working_tree_after_add=repaired)
        self.assertTrue(stale, "the checkout edit reached the cache without a reinstall")
        self.assertTrue(repaired, "`codex plugin add` did not pick up the checkout edit")


if __name__ == "__main__":
    unittest.main()
