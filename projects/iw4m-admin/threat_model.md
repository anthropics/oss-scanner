# IW4MAdmin threat model

## What it does
IW4MAdmin is a .NET 10 server administration tool for Call of Duty (IW4x, Plutonium T4/T5/T6/IW5, etc.) and some
Source-engine game servers. It connects to game servers over RCon (UDP), tails their game logs, tracks players and
statistics in a database (SQLite by default; MySQL/PostgreSQL optional), runs in-game commands, and hosts a web
front end (ASP.NET Core, `WebfrontCore`) with a REST-style API. It is extensible through compiled C# plugins and C# script plugins (`Plugins/ScriptPlugins`).

## Where untrusted input enters
- **Game log lines and RCon responses** (`Integrations/`, `Application/EventParsers`, `Application/RConParsers`):
  player names, chat messages, GUIDs and IPs are attacker-controlled by anyone who joins a server.
- **In-game chat commands** (`SharedLibraryCore/Commands`, `Application/Commands`): any player can issue commands;
  the permission system decides what is allowed.
- **Web front end and API** (`WebfrontCore/Controllers`): reachable by unauthenticated users on the network;
  authenticated users have levels from User up to Owner.
- **Plugins** (`Plugins/`): first-party plugins (Stats, Login, LiveRadar, Mute, etc.) and the script plugins in
  `Plugins/ScriptPlugins` (including game-specific event and RCon parsers) process the same untrusted inputs.

## In scope
- Authentication or authorization bypass in the web front end, API, or in-game command permission checks.
- Privilege escalation between permission levels (e.g., a player or moderator acting as an admin/owner).
- Injection (SQL, RCon command injection via player names/chat, XSS in the web front end, log injection that
  causes forged events).
- Path traversal, SSRF, deserialization, and remote code execution.
- Denial of service that a single remote player or unauthenticated web user can trigger cheaply.

## Out of scope / lower severity
- Attacks requiring Owner-level access, or control of the host machine, configuration files, or the game server itself.
- Game-server (engine) vulnerabilities and anti-cheat evasion.
- Third-party script plugins not shipped in this repository.

## Severity guidance
- Unauthenticated RCE, auth bypass to admin, or RCon command injection from a player name/chat: **critical**.
- Stored XSS reachable by unauthenticated users or players, and SQLi: **high**.
- Issues requiring an authenticated privileged (Moderator+) account: cap at **medium** unless they reach RCE.
