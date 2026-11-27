"""C1: do the list commands write anything, and do they touch the network?

Pass condition (spec §12): the harness home is identical before and after each list command, run
with networking blocked. `--dry-run` relies on this (spec §8): a list command that writes is
dropped from dry-run for that harness.

Each harness is first given a marketplace and an installed plugin, and every list command is run
once to absorb first-run initialisation. Then each list command runs again between two snapshots
of the whole temp HOME, and the sandbox log is read for outbound connections it attempted. The
first-run writes are recorded too, separately: they are what a dry-run would do on a machine where
the harness has never run.

The assertion is on the environment agent-sync gives each list call (spec §4): passed through
unchanged for Codex and agy, and with `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` for Claude's two
list calls. Without that variable each Claude list call queues a telemetry file and tries an
outbound connection; that environment, and `DISABLE_TELEMETRY=1`, are measured and recorded only.
"""

import datetime
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness as h  # noqa: E402

LISTS = {
    "claude": [
        ["claude", "plugin", "marketplace", "list", "--json"],
        ["claude", "plugin", "list", "--json"],
    ],
    "codex": [
        ["codex", "plugin", "marketplace", "list", "--json"],
        ["codex", "plugin", "list", "--marketplace", h.MARKETPLACE, "--json"],
    ],
    "agy": [
        ["agy", "plugin", "list", "--json"],
    ],
}


class ListCommandsCase(h.ContractCase):
    TEST_ID = "C1"
    HARNESS = None
    ASSERTED_ENV = None  # the environment agent-sync gives these list calls
    RECORDED_ENVS = ()   # measured and recorded, not asserted

    def measure(self, argv, extra_env=None):
        """Writes and attempted connections of one list call.

        The sandbox log has one-second resolution, so each call gets a window of its own.
        """
        before = h.snapshot(self.iso.home)
        time.sleep(1.1)
        started = datetime.datetime.now()
        self.ok("steady-state list", argv, extra_env=extra_env)
        ended = datetime.datetime.now()
        time.sleep(1.1)
        diff = h.diff_snapshots(before, h.snapshot(self.iso.home))
        denied = h.sandbox_denials(started, "network-outbound", until=ended)
        h.record(self.iso, self.TEST_ID, "steady-state list observation", argv=argv,
                 extra_env=extra_env or {}, diff=diff, network_denials=denied)
        return diff, denied

    def install_one(self):
        raise NotImplementedError

    def test_list_commands_write_nothing_and_stay_offline(self):
        # First-ever calls, in a home the harness has not seen.
        for argv in LISTS[self.HARNESS]:
            before = h.snapshot(self.iso.home)
            self.ok("first-run list", argv)
            h.record(self.iso, self.TEST_ID, "first-run writes",
                     argv=argv, diff=h.diff_snapshots(before, h.snapshot(self.iso.home)))

        self.prove_isolated(self.HARNESS)
        self.install_one()
        for argv in LISTS[self.HARNESS]:
            self.ok("warm-up list", argv)

        for extra_env in self.RECORDED_ENVS:
            for argv in LISTS[self.HARNESS]:
                self.measure(argv, extra_env)
        writes = {}
        network = {}
        for argv in LISTS[self.HARNESS]:
            diff, denied = self.measure(argv, self.ASSERTED_ENV)
            key = " ".join(argv)
            if any(diff.values()):
                writes[key] = diff
            if denied:
                network[key] = denied

        self.assertEqual(writes, {}, "list commands wrote to the harness home")
        self.assertEqual(network, {}, "list commands attempted outbound connections")


class ClaudeLists(ListCommandsCase):
    HARNESS = "claude"
    NEEDS = ("claude", "git")
    ASSERTED_ENV = {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    RECORDED_ENVS = ({}, {"DISABLE_TELEMETRY": "1"})

    def install_one(self):
        catalog = self.iso.make_catalog()
        self.ok("setup: marketplace add",
                ["claude", "plugin", "marketplace", "add", "--json", catalog])
        self.ok("setup: install", ["claude", "plugin", "install", "--json",
                                   "alpha@%s" % h.MARKETPLACE])


class CodexLists(ListCommandsCase):
    HARNESS = "codex"
    NEEDS = ("codex", "git")

    def install_one(self):
        catalog = self.iso.make_catalog()
        self.ok("setup: marketplace add",
                ["codex", "plugin", "marketplace", "add", "--json", "--ref", "main",
                 self.git_url_for(catalog)])
        self.ok("setup: plugin add", ["codex", "plugin", "add", "--json",
                                      "alpha@%s" % h.MARKETPLACE])


class AgyLists(ListCommandsCase):
    HARNESS = "agy"
    NEEDS = ("agy", "git")

    def install_one(self):
        catalog = self.iso.make_catalog()
        self.ok("setup: plugin install",
                ["agy", "plugin", "install", os.path.join(catalog, "plugins", "alpha")])


del ListCommandsCase  # keep discovery from collecting the base class

if __name__ == "__main__":
    unittest.main()
