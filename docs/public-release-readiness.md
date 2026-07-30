# Public release readiness

Changing repository visibility is a separate release decision. A passing
Skill release gate does not establish that Git history, GitHub metadata, or
hosted assets are safe to disclose.

## Required before visibility changes

- The current source tree contains only public or synthetic evaluation inputs.
- Published assets contain no private-repository-derived records, personal
  data, credentials, or machine-specific paths.
- Git history and commit author metadata have been reviewed for the same
  classes of information.
- Issue, Pull Request, Actions, and Release histories have been reviewed.
- A root distribution license has been selected by the copyright owner.
- Private vulnerability reporting is enabled.
- The public candidate is installed and smoke-tested from a clean checkout.

## Published boundary

The committed pilot directory is a public source registry only. Complete audit
runs, reviewer records, human labels, and private-repository-derived evidence
are excluded from this repository. This public repository was created from the
reviewed source tree with a new Git history; the earlier development archive,
its hosted assets, and its collaboration metadata remain private.

The preferred publication path is a new, clean public history generated from
the reviewed tree. Rewriting an established repository is acceptable only with
an explicit owner decision, complete backup, tag and release replacement plan,
and post-rewrite verification.
