# Contributing to Gizpix

Thanks for helping. Short rules:

1. **Licence of your contribution.** Gizpix is distributed under AGPL-3.0-or-later and, by separate agreement, under commercial terms. By opening a pull request you agree that your contribution is licensed to the project under the **MIT licence**, so the maintainer can distribute it under both. Do not send code you do not have the right to license this way (for example code copied from another project).
2. **Keep it local and small.** Gizpix is offline: no network calls, no AI calls, no telemetry. Tools measure or repair; they do not draw art they were not given.
3. **Tests.** Run `python gizpix.py doctor` (every self-test) and `python -m pytest` before you send a change. Add a self-check for non-trivial logic.
4. **Headers.** New Python files start with `# SPDX-License-Identifier: AGPL-3.0-or-later`.
5. **Pictures and samples.** Do not add sprites you did not make or that have unclear terms. Sample frames are drawn by `samples/make_samples.py`.

Report bugs with the exact command, the Python and Pillow versions and, if you can, a small PNG that shows the problem.
