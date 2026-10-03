# Security Policy

## Supported versions

Security fixes are released for the latest minor version of leafpress. Please upgrade to the most recent release before reporting.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report vulnerabilities privately through GitHub:
[**Report a vulnerability**](https://github.com/hutchins/leafpress/security/advisories/new) (Security tab → "Report a vulnerability").

Include the leafpress version, how you ran it (CLI, Docker, GitHub Action), and a minimal reproduction if possible. You should receive a response within a few days. We'll coordinate a fix and disclosure timeline with you.

## Scope and threat model

leafpress often converts repositories the operator doesn't control: git URL sources, monorepo `projects[].url`, and CI checkouts of contributor branches. Content from such repositories must not be able to:

- read files outside the project, or reach internal network hosts;
- run code, or change how git and other tools run;
- inject active content (scripts, event handlers) into generated documents, when HTML sanitizing is enabled.

See [Remote Sources → Converting untrusted repositories](https://leafpress.dev/remote-sources/#converting-untrusted-repositories) for the protections in place. Bypasses of any of these are in scope.
