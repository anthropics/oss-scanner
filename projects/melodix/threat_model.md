# Melodix threat model

Melodix is a self-hosted Discord music bot and terminal player written in Go.
It accepts commands and URLs from Discord users, retrieves metadata and audio
from external services, and can invoke external media tools such as ffmpeg and
yt-dlp.

## In scope

- Parsing and handling of user-provided commands, URLs, playlists, metadata,
  and remote media responses.
- Network-facing Discord gateway and voice-session handling, including
  reconnect and recovery paths.
- Process invocation, argument construction, and output handling for external
  media tools.
- Persistence and cache handling, including malformed or interrupted state.
- Vulnerabilities in first-party code and security-relevant dependency use.

Treat externally supplied URLs, metadata, media bytes, and Discord input as
untrusted. Do not assume that a supported provider always returns well-formed
or benign content.

## Severity guidance

- Critical: unauthenticated remote code execution, credential compromise, or
  a similarly broad compromise of a host running the bot.
- High: exploitable code execution, arbitrary file access, or significant
  compromise requiring limited user interaction or configuration.
- Medium: meaningful denial of service, data exposure, or integrity impact
  with practical but narrower preconditions.
- Low: issues with limited impact or requiring unlikely local conditions.

Please distinguish demonstrated impact from theoretical concerns and include
reproduction steps that do not require real Discord credentials or private
service accounts. Do not run live tests that contact third-party media services
or Discord; the repository's opt-in live tests should remain disabled.

## How to exercise it

Use the unit and package tests in the repository. The scanner image builds both
the Discord bot and CLI and runs `go test -race ./...` before the network is
disabled. The built binaries and source remain in `/src` for offline analysis.
