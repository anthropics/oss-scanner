# winresizer security review

## Purpose and trust boundaries

winresizer is a Vim plugin for interactively resizing, moving, and focusing editor
windows. It has no network listener and does not intentionally execute buffer
contents. The user's Vim configuration and deliberately installed plugins are
trusted code, and ordinary editor commands issued by the user are authorized.

Review `plugin/` and `autoload/`, especially any path where buffer names, file
names, window state, or input events could affect Vim command construction or
cause unintended actions. A useful security finding needs a concrete boundary,
such as opening an attacker-controlled filename leading to unintended command
execution. An attacker who can already edit vimrc has arbitrary editor code
execution; do not report that capability alone as a plugin vulnerability.

## Environment and exercising the project

Source is in `/src`. Vim, Neovim, and the project's pinned Vader test submodule
are installed. Run the existing suite from `/src` with:

    vim -Es -u test/vimrc '+Vader! test/winresizer.vader'

Interactive behavior may need a pseudo-terminal. The Linux environment covers
terminal Vim; MacVim GUI behavior needs separate platform validation and should
be identified as such in reports. The plugin has no compilation step.

## Impact and reporting

Prioritize unintended command execution, disclosure, file modification, or data
loss reachable through untrusted input. Distinguish a security boundary violation
from expected window closure or a layout bug triggered by a local user. Assess
availability issues in the context of a local editor, without assuming a server.

Include the minimal vimrc, Vim/Neovim version, exact files and keystrokes, relevant
options, root cause, and a minimal patch or regression test when feasible.
Deduplicate by root cause. Vulnerabilities solely in Vim, Neovim, Vader, or an
unrelated installed plugin are outside this project's scope unless winresizer
introduces a distinct reachable security issue.
