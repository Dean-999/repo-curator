# Security Policy

repo-curator treats every inspected repository and supplied export as
untrusted data. A vulnerability that permits target-code execution, path
escape, unsafe link following, secret persistence, unauthorized mutation, or
evidence-integrity bypass is considered security-sensitive.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in a public Issue or Pull Request.
Use GitHub's private vulnerability reporting flow from the repository
**Security** tab. Include:

- the affected version or commit;
- the smallest non-sensitive reproduction;
- the expected and observed safety boundary;
- whether any target content, secret, or filesystem path may have been
  exposed or modified.

Do not include real credentials, private repository content, personal data, or
production research data. Replace them with synthetic values.

## Supported versions

Security fixes are applied to the latest published release and the default
branch. Older releases may receive a replacement only when the same fix can be
backported without weakening current safety contracts.

## Disclosure

The maintainer will acknowledge a complete report, assess scope, and coordinate
disclosure after a fix and regression test are available. No response-time SLA
is promised.
