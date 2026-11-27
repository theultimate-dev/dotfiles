"""C2: is a plugin from a Claude directory marketplace read live, or copied at install?

Pass condition (spec §12): after install, edit a fixture skill in the checkout; a fresh
`claude plugin list --json` and the plugin's component inventory show the edit (live) or not
(copied). The spec assumes live (§5.1, "A checkout marketplace is never updated"); a copied result
fails this test, because it changes that section.

Claude still writes a copy into its plugin cache at install. What decides "live" is which tree
Claude reads afterwards: `plugin list` names it as `readFromFolder`, and `plugin details` builds
its inventory from it. A model session is not started (none is available offline); confirming
the same in a session belongs with the manual C7.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness as h  # noqa: E402

PLUGIN = "alpha@%s" % h.MARKETPLACE


class ClaudeDirectoryMarketplace(h.ContractCase):
    TEST_ID = "C2"
    NEEDS = ("claude", "git")

    def details(self, step):
        return self.ok(step, ["claude", "plugin", "details", PLUGIN]).stdout

    def test_checkout_edits_are_read_live(self):
        self.prove_isolated("claude")
        checkout = self.iso.make_catalog()
        plugin_dir = os.path.join(checkout, "plugins", "alpha")
        self.ok("marketplace add (directory)",
                ["claude", "plugin", "marketplace", "add", "--json", checkout])
        self.ok("install", ["claude", "plugin", "install", "--json", PLUGIN])
        entry = self.ok("list after install", ["claude", "plugin", "list", "--json"]).json()[0]
        install_path = entry["installPath"]
        cache_digest_at_install = h.tree_digest(install_path)
        self.assertNotIn("alpha-added", self.details("details before edit"))

        # Uncommitted edits: a changed SKILL.md and a new skill.
        h.write_skill(plugin_dir, "alpha-skill", "Edited in the checkout after install.")
        h.write_skill(plugin_dir, "alpha-added", "Added in the checkout after install.")

        entry_after = self.ok("list after edit", ["claude", "plugin", "list", "--json"]).json()[0]
        details_after = self.details("details after edit")
        cache_changed = h.tree_digest(install_path) != cache_digest_at_install
        read_from = entry_after.get("readFromFolder")
        inventory_live = "alpha-added" in details_after
        h.record(self.iso, self.TEST_ID, "observation",
                 list_entry_after_edit=entry_after,
                 read_from_folder_is_checkout=(
                     read_from is not None
                     and os.path.realpath(read_from) == os.path.realpath(plugin_dir)),
                 install_path_is_cache=install_path.startswith(self.iso.claude_home),
                 cache_copy_changed_by_edit=cache_changed,
                 inventory_shows_new_skill=inventory_live,
                 verdict="live" if inventory_live else "copied")

        # What the marketplace and plugin "update" verbs do for a directory source: agent-sync
        # never runs them for a checkout, but the docs say what they would do.
        self.run_cli("marketplace update (directory)",
                     ["claude", "plugin", "marketplace", "update", "--json", h.MARKETPLACE])
        upd = self.run_cli("plugin update (directory)",
                           ["claude", "plugin", "update", "--scope", "user", "--json", PLUGIN])
        h.record(self.iso, self.TEST_ID, "after plugin update",
                 returncode=upd.returncode,
                 cache_copy_changed=h.tree_digest(install_path) != cache_digest_at_install,
                 list_entry=self.ok("list after update",
                                    ["claude", "plugin", "list", "--json"]).json())

        self.assertTrue(inventory_live,
                        "Claude did not pick up a checkout edit: the plugin is copied at install")
        self.assertEqual(os.path.realpath(read_from), os.path.realpath(plugin_dir))


if __name__ == "__main__":
    unittest.main()
