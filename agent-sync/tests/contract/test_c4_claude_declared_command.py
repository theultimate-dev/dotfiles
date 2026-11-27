"""C4: what does `claude plugin install --json` print for a declared command without `-y`?

Pass condition (spec §12): a JSON line with `shownCommand.sha256`; non-zero exit; nothing
installed; `--accept-command` with that hash installs.

The fixture catalog declares a `command`-source plugin: a command that prints the path of a plugin
directory, which Claude copies into its cache. The command also touches a marker file, so the test
can tell whether it ran. The test records the full held result (spec §5.1 builds `held` rows on
it), a wrong hash, and three catalog changes: (a) the catalog moves under an accepted, unchanged
command; (b) a fresh install with a hash shown before the move; (c) the command itself changes.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness as h  # noqa: E402

PLUGIN = "cmdplug@%s" % h.MARKETPLACE


class ClaudeDeclaredCommand(h.ContractCase):
    TEST_ID = "C4"
    NEEDS = ("claude", "git")

    def make_command_catalog(self):
        produced = os.path.join(self.iso.work, "produced-plugin")
        os.makedirs(os.path.join(produced, ".claude-plugin"))
        h.write_json(os.path.join(produced, ".claude-plugin", "plugin.json"), {
            "name": "cmdplug", "version": "0.1.0", "description": "Command-sourced fixture."})
        h.write_skill(produced, "cmd-skill", "Produced by a command.")
        self.marker = os.path.join(self.iso.work, "command-ran")
        # Printable ASCII, single spaces: the schema refuses anything else.
        self.command = "/usr/bin/touch %s && /bin/echo %s" % (self.marker, produced)
        entry = {
            "name": "cmdplug",
            "description": "Command-sourced fixture.",
            "version": "0.1.0",
            "source": {"source": "command", "command": self.command},
        }
        return self.iso.make_catalog(extra_entries=[entry])

    def installed_ids(self, step):
        return [p["id"] for p in self.ok(step, ["claude", "plugin", "list", "--json"]).json()]

    def install(self, step, *extra):
        r = self.run_cli(step, ["claude", "plugin", "install", "--scope", "user", "--json"]
                         + list(extra) + [PLUGIN])
        return r, r.json_lines()

    def test_declared_command_is_held_then_accepted_by_hash(self):
        self.prove_isolated("claude")
        catalog = self.make_command_catalog()
        self.ok("marketplace add (git)",
                ["claude", "plugin", "marketplace", "add", "--json", self.git_url_for(catalog)])

        held, lines = self.install("install without -y")
        result = lines[-1] if lines else {}
        shown = result.get("shownCommand") or {}
        non_json = [ln for ln in held.stdout.splitlines() if ln.strip() and not
                    ln.lstrip().startswith("{")]
        h.record(self.iso, self.TEST_ID, "held result shape",
                 returncode=held.returncode, json_line=result,
                 json_lines_on_stdout=len(lines), human_lines_before_json=len(non_json),
                 json_is_last_line=held.stdout.strip().splitlines()[-1].lstrip().startswith("{"),
                 command_ran=os.path.exists(self.marker))
        self.assertNotEqual(held.returncode, 0)
        self.assertRegex(shown.get("sha256", ""), r"^[0-9a-f]{64}$")
        self.assertFalse(os.path.exists(self.marker), "the declared command ran without consent")
        self.assertNotIn(PLUGIN, self.installed_ids("list after held install"))

        wrong, wrong_lines = self.install("install with a wrong hash", "--accept-command", "0" * 64)
        h.record(self.iso, self.TEST_ID, "wrong hash", returncode=wrong.returncode,
                 json_line=wrong_lines[-1] if wrong_lines else None,
                 command_ran=os.path.exists(self.marker))
        self.assertNotEqual(wrong.returncode, 0)
        self.assertFalse(os.path.exists(self.marker))

        accepted, acc_lines = self.install("install with the shown hash",
                                           "--accept-command", shown["sha256"])
        h.record(self.iso, self.TEST_ID, "accepted", returncode=accepted.returncode,
                 json_line=acc_lines[-1] if acc_lines else None,
                 command_ran=os.path.exists(self.marker))
        self.assertEqual(accepted.returncode, 0)
        self.assertTrue(os.path.exists(self.marker))
        self.assertIn(PLUGIN, self.installed_ids("list after accepted install"))

        # (a) The catalog moves, the command does not: does `update` of the accepted plugin hold?
        self.move_catalog(catalog, "README.md", "Catalog moved.\n")
        self.observe("a: update, command unchanged, catalog moved",
                     ["update", "--scope", "user", "--json", PLUGIN])

        # (b) A fresh install with the hash shown before the catalog moved.
        self.ok("uninstall", ["claude", "plugin", "uninstall", "--scope", "user", "--json",
                              PLUGIN])
        b = self.observe("b: install with the pre-move hash",
                         ["install", "--scope", "user", "--json", "--accept-command",
                          shown["sha256"], PLUGIN])
        b_shown = (b or {}).get("shownCommand") or {}
        if b_shown.get("sha256"):
            self.observe("b: install with the hash shown after the move",
                         ["install", "--scope", "user", "--json", "--accept-command",
                          b_shown["sha256"], PLUGIN])

        # (c) The command itself changes: does `update` hold, and which hash does it take?
        changed = "/usr/bin/true && " + self.command
        self.rewrite_command(catalog, changed)
        c = self.observe("c: update, command changed, no hash",
                         ["update", "--scope", "user", "--json", PLUGIN])
        self.observe("c: update, command changed, pre-change hash",
                     ["update", "--scope", "user", "--json", "--accept-command",
                      shown["sha256"], PLUGIN])
        c_shown = (c or {}).get("shownCommand") or {}
        if c_shown.get("sha256"):
            self.observe("c: update, command changed, its new hash",
                         ["update", "--scope", "user", "--json", "--accept-command",
                          c_shown["sha256"], PLUGIN])

    # -- helpers for the catalog-change cases -------------------------------------------------

    def observe(self, step, args):
        """Run one `claude plugin …` call with the marker cleared; record outcome and whether
        the declared command ran. Returns the result's last JSON line."""
        if os.path.exists(self.marker):
            os.remove(self.marker)
        r = self.run_cli(step, ["claude", "plugin"] + args)
        lines = r.json_lines()
        last = lines[-1] if lines else None
        h.record(self.iso, self.TEST_ID, step + " (summary)", returncode=r.returncode,
                 json_line=last, command_ran=os.path.exists(self.marker),
                 installed=PLUGIN in self.installed_ids(step + ": list"))
        return last

    def move_catalog(self, catalog, name, text):
        with open(os.path.join(catalog, name), "w") as f:
            f.write(text)
        self.iso.commit_all(catalog, "move the catalog")
        self.ok("marketplace update", ["claude", "plugin", "marketplace", "update", "--json",
                                       h.MARKETPLACE])

    def rewrite_command(self, catalog, command):
        path = os.path.join(catalog, ".claude-plugin", "marketplace.json")
        with open(path) as f:
            doc = json.load(f)
        for entry in doc["plugins"]:
            if entry["name"] == "cmdplug":
                entry["source"]["command"] = command
        h.write_json(path, doc)
        self.iso.commit_all(catalog, "change the declared command")
        self.ok("marketplace update", ["claude", "plugin", "marketplace", "update", "--json",
                                       h.MARKETPLACE])


if __name__ == "__main__":
    unittest.main()
