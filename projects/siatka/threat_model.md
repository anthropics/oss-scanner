# siatka — threat model

## What it is
A deterministic, offline content-safety filter for Polish text (regular expressions only, stdlib `re`/`typing`, no network, no model).
It classifies a user utterance as crisis / violence / medical emergency / child-unsafe and returns a category; the host application
(a household voice assistant) then shows a fixed emergency message (112 and Polish helplines).

## Where untrusted input enters
The single public entry point takes an arbitrary user string (speech-to-text output or chat text, possibly very long,
possibly adversarial, any Unicode). That string is the only untrusted input.

## What we care about (severity guidance)
- **Critical:** input that makes the filter crash, hang, or take super-linear time (ReDoS / catastrophic backtracking) — a hung
  filter means a child in danger gets no emergency message.
- **High:** a genuine emergency phrasing that is silently missed because of a code defect (normalisation bug, exception swallowed,
  wrong category ordering) rather than vocabulary coverage.
- **Medium:** exceptions on unusual Unicode, memory blow-up on large input.
- **Out of scope:** missing vocabulary / linguistic coverage gaps (tracked as quality issues), false positives on benign text,
  anything in the host application.

## Reports
Please include the triggering input string and timing; a patch with a regression test in `tests/` is ideal.
