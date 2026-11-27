"""C5: what does `codex plugin marketplace remove` do to plugins installed from it?

Recorded for docs/agent-sync.md (spec §5.2, "A ref mismatch is reported, never fixed"); agent-sync
never calls it. The test asserts only its own setup; the behaviour is written to the results.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness as h  # noqa: E402

PLUGIN = "alpha@%s" % h.MARKETPLACE


class CodexMarketplaceRemove(h.ContractCase):
    TEST_ID = "C5"
    NEEDS = ("codex", "git")

    def state(self, step):
        cfg = os.path.join(self.iso.codex_home, "config.toml")
        cache = os.path.join(self.iso.codex_home, "plugins", "cache", h.MARKETPLACE)
        root = os.path.join(self.iso.codex_home, ".tmp", "marketplaces", h.MARKETPLACE)
        listed = self.run_cli(step + ": plugin list",
                              ["codex", "plugin", "list", "--marketplace", h.MARKETPLACE,
                               "--json"])
        everything = self.run_cli(step + ": plugin list (all)",
                                  ["codex", "plugin", "list", "--json"])
        markets = self.run_cli(step + ": marketplace list",
                               ["codex", "plugin", "marketplace", "list", "--json"])
        with open(cfg) as f:
            config = f.read()
        obs = {
            "marketplaces": [m["name"] for m in (markets.json() or {}).get("marketplaces", [])],
            "installed_in_marketplace": [p["pluginId"] for p in
                                         (listed.json() or {}).get("installed", [])],
            "installed_anywhere": [p["pluginId"] for p in
                                   (everything.json() or {}).get("installed", [])],
            "plugin_cache_tree": sorted(h.snapshot(cache)),
            "marketplace_snapshot_present": os.path.isdir(root),
            "config_toml": config,
        }
        h.record(self.iso, self.TEST_ID, step, observation=obs)
        return obs

    def test_record_marketplace_remove(self):
        self.prove_isolated("codex")
        catalog = self.iso.make_catalog()
        url = self.git_url_for(catalog)
        add = ["codex", "plugin", "marketplace", "add", "--json", "--ref", "main", url]
        remove = ["codex", "plugin", "marketplace", "remove", "--json", h.MARKETPLACE]
        self.ok("marketplace add (git)", add)
        self.ok("plugin add", ["codex", "plugin", "add", "--json", PLUGIN])
        before = self.state("1 before remove")
        self.assertEqual(before["installed_in_marketplace"], [PLUGIN])

        # Path 1: remove the marketplace, then add the same source back.
        self.run_cli("1 marketplace remove", remove)
        self.state("1 after marketplace remove")
        self.run_cli("1 marketplace re-add", add)
        self.state("1 after re-add, no plugin add")

        # Path 2: remove it again, then try the plugin verbs while it is gone.
        self.run_cli("2 marketplace remove", remove)
        self.run_cli("2 plugin add with the marketplace removed",
                     ["codex", "plugin", "add", "--json", PLUGIN])
        self.run_cli("2 plugin remove with the marketplace removed",
                     ["codex", "plugin", "remove", "--json", PLUGIN])
        self.state("2 after plugin remove")
        self.run_cli("2 marketplace re-add", add)
        self.state("2 after re-add, no plugin add")


if __name__ == "__main__":
    unittest.main()
