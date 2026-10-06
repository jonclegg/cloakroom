"""Cloakroom's notebook: what it learned about each site, kept between runs.

Two kinds of entry per site, under <data>/notes/sites/:

* <site>.md     lessons the model wrote itself ("cars.com: the photo gallery opens
                from the main image; Esc closes it").
* <site>.jsonl  the run log, written by Cloakroom after every run that touched
                the site: the message, outcome, bot checks seen, steps, cost.

Lessons that are not about one site go to <data>/notes/general.md. Lookup is by
exact domain: the browser's current host names the site, so there is nothing to
search.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time

NOTES_SHOWN = 30
GENERAL_SHOWN = 15
RUNS_SHOWN = 5


class Notebook:
    def __init__(self, data_dir):
        self.root = os.path.join(data_dir, "notes")
        self.sites_dir = os.path.join(self.root, "sites")
        os.makedirs(self.sites_dir, exist_ok=True)
        self.lock = threading.Lock()

    def _path(self, site, suffix):
        if site == "general":
            return os.path.join(self.root, "general.md")
        if not re.fullmatch(r"[a-z0-9.-]+", site):
            raise ValueError(f"not a site name: {site!r}")
        return os.path.join(self.sites_dir, site + suffix)

    def add_note(self, site, text, run_id):
        line = f"- {time.strftime('%Y-%m-%d')} ({run_id}): {' '.join(text.split())}\n"
        with self.lock, open(self._path(site, ".md"), "a") as fh:
            fh.write(line)

    def log_run(self, site, entry):
        with self.lock, open(self._path(site, ".jsonl"), "a") as fh:
            fh.write(json.dumps(entry) + "\n")

    def notes_for(self, site, limit=NOTES_SHOWN):
        path = self._path(site, ".md")
        if not os.path.exists(path):
            return ""
        with self.lock, open(path) as fh:
            return "".join(fh.readlines()[-limit:]).strip()

    def runs_for(self, site, limit=RUNS_SHOWN):
        path = self._path(site, ".jsonl")
        if not os.path.exists(path):
            return []
        with self.lock, open(path) as fh:
            return [json.loads(line) for line in fh.readlines()[-limit:]]

    def context_for(self, site):
        """The notebook section of the prompt for the site the browser is on."""
        parts = []
        general = self.notes_for("general", GENERAL_SHOWN)
        if general:
            parts.append(f"General:\n{general}")
        if site:
            notes = self.notes_for(site)
            if notes:
                parts.append(f"{site}:\n{notes}")
            runs = self.runs_for(site)
            if runs:
                lines = [
                    f"- {run['time'][:16]} {run['status']}: {run['message'][:80]!r}"
                    + (f" bot checks: {', '.join(run['blocks'])}" if run["blocks"] else "")
                    for run in runs
                ]
                parts.append(f"Recent runs on {site}:\n" + "\n".join(lines))
        return "\n\n".join(parts) or "(nothing yet)"

    def sites(self):
        names = {
            name.rsplit(".", 1)[0]
            for name in os.listdir(self.sites_dir)
            if name.endswith((".md", ".jsonl"))
        }
        return sorted(names)
