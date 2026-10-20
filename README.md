# Redline

A spec-driven, test-first development tool for working with AI agents. A requirement isn't real
until a test has proved it can fail.

Status: being built, in the order of [docs/design.md](docs/design.md) §11; steps 1–6 are on `main`.

## Rules that hold from the first commit

Redline is built the way it asks others to work:

- Every PR changes at most 400 lines.
- One session per step. A merge ends the session, with a hand-off prompt for the next one.
- Tests come first, and each one is seen to fail before the code that makes it pass.
