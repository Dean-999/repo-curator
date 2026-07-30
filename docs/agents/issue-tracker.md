# Issue tracker: GitHub

Issues and PRDs for this repository live as GitHub issues in `Dean-999/repo-curator`. Use the `gh` CLI for issue operations and infer the repository from the local `origin` remote.

## Conventions

- Create an issue with `gh issue create` and a multiline body.
- Read an issue and its discussion with `gh issue view <number> --comments`.
- List issues with `gh issue list`, requesting structured JSON when filtering or summarizing.
- Comment with `gh issue comment <number>`.
- Apply or remove labels with `gh issue edit <number> --add-label` or `--remove-label`.
- Close an issue with `gh issue close <number> --comment`.

## Pull requests as a triage surface

External pull requests are **not** a request surface. Pull requests do not enter the issue triage state machine merely because they are external contributions.

GitHub shares one number space across issues and pull requests. Resolve an ambiguous reference before acting on it.

## Skill vocabulary

When a skill says “publish to the issue tracker,” create a GitHub issue. When it says “fetch the relevant ticket,” read the complete GitHub issue body, labels, and comments.
