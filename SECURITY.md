# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in Op3, please report it
responsibly by emailing **ksk5429@snu.ac.kr**.

Please do NOT open a public GitHub issue for security vulnerabilities.

You can expect:
- Acknowledgment within 48 hours
- Assessment within 1 week
- A fix or mitigation plan within 2 weeks for confirmed vulnerabilities

## Scope

Op3 is a research framework that processes numerical simulation data.
It does not handle user authentication, payment data, or personal
information. The primary security concerns are:

- **Proprietary data exposure**: OptumGX results may contain
  site-specific data protected by NDA. The `<REDACTED>` pattern
  in the codebase prevents accidental disclosure.
- **Dependency vulnerabilities**: Op3 depends on numpy, scipy,
  pandas, openseespy, and other packages. Dependabot monitors
  these automatically.
- **Pickle/deserialization**: Op3 does not use pickle or eval on
  untrusted input.
