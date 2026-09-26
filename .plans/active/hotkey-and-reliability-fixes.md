# Feature: Hotkey & Reliability Fixes

## Metadata
- **Status**: `testing`
- **Created**: 2026-09-25
- **Last Updated**: 2026-09-25
- **Priority**: `high`

## Overview
Fix the day-to-day annoyances in dictation: the hotkey triggered Redo in the focused app, dictating wiped the clipboard, accidental taps/silence pasted Whisper hallucinations ("Thank you."), UI updates from background threads could crash the app, and overlapping dictations clobbered each other.

## Requirements
- [x] Hold **Right Option** to transcribe (replaces Cmd+Shift+Z, which was Redo in most apps)
- [x] Hold **Right Command** for Claude mode (replaces Cmd+Shift+A)
- [x] Pressing any other key while holding the hotkey cancels (keeps Option+←, Cmd+C etc. working)
- [x] Quick taps do nothing (150ms hold delay before recording starts)
- [x] Restore the user's clipboard after pasting (all types: text, images, rich text, files)
- [x] Skip recordings < 0.3s and silent recordings instead of sending them to Whisper
- [x] Clip audio before int16 conversion (loud input no longer wraps/distorts)
- [x] All UI updates (menubar title, status, notifications) on the main thread
- [x] Busy guard: holding the hotkey while processing plays "Funk" and doesn't start a new recording
- [x] README and menu labels updated

## Technical Approach

### Hotkeys
Modifier-only hotkeys send no keystroke to the focused app, so there's nothing to suppress (the original plan's attempts with Option+Space typed spaces). pynput reports `Key.alt_r` / `Key.cmd_r` distinctly on macOS.

State machine, guarded by `self.lock` (listener, hold timer, and worker threads all touch it):
- `state`: `idle` → `recording` → `processing` → `idle`
- `held_hotkey` + `hotkey_combo` track the physical key, independent of `state`
- Hotkey press arms a `threading.Timer(HOLD_DELAY)`. When it fires: busy → Funk; idle → start recording
- Any other key while held → `hotkey_combo = True`, cancel timer / discard recording
- Hotkey release → stop recording and process in a worker thread

pynput quirks handled:
- **Twin modifiers**: pynput derives modifier press/release from the flag mask, so releasing Right Option while Left Option is held is reported as a *press* of `alt_r`. Modifiers don't auto-repeat, so a repeat press of the held hotkey is treated as a release.
- **Injected events** (our own osascript Cmd+V) are ignored via pynput's `injected` callback arg.
- **Exceptions in callbacks stop the listener permanently** (pynput re-raises and stops), so callbacks catch everything and notify instead.
- Stream stop/close happens off the listener thread.

### Clipboard
`paste_text()` snapshots every pasteboard item/type via `NSPasteboard`, writes our text (marked `org.nspasteboard.TransientType` so clipboard managers skip it), sends Cmd+V, waits `CLIPBOARD_RESTORE_DELAY` (0.5s) and restores. It skips the restore if `changeCount` moved (user copied something meanwhile). If the paste fails, the text is left on the clipboard for a manual Cmd+V.

### Silence detection
`is_silent()`: loudest 50ms window RMS < `SILENCE_THRESHOLD` (default 0.005 ≈ -46 dBFS, overridable in `.env`). Deliberately conservative: it only catches near-true silence, since dropping real speech is worse than an occasional hallucination.

### Main thread
`on_main_thread()` wraps `PyObjCTools.AppHelper.callAfter` (rumps runs `AppHelper.runEventLoop`). `notify()` routes notifications through it.

### Files to Modify/Create
| File | Action | Description |
|------|--------|-------------|
| `overtone.py` | modify | Hotkeys, state machine, clipboard restore, silence skip, main-thread UI |
| `README.md` | modify | New hotkeys, Funk sound, SILENCE_THRESHOLD, troubleshooting |

## Progress Log
<!-- Append new entries at the top. This is the session continuity record. -->

### 2026-09-25 (later)
**Session**: Debugging "no text appears"
**Done**:
- Root cause: OpenAI account out of credits (429). The error notification never showed (notifications don't appear for this Python), so it looked silent
- Made transcription endpoint configurable, generically: `TRANSCRIBE_API_KEY` / `TRANSCRIBE_BASE_URL` / `TRANSCRIBE_MODEL`, plus `API_USER` (sent as `user` on every request, for proxy attribution)
- Scale setup lives only in the gitignored `.env`: LiteLLM proxy from toolbox, `groq/whisper-large-v3-turbo` (0.4s vs 1.5s for whisper-1)
- Findings: the LiteLLM proxy ignores the `x-litellm-project-id` header on audio uploads, but accepts `user=<project id>`; it returns JSON even for `response_format="text"`, so we read `.text` from the default JSON response
- Verified end to end: real app code transcribes a `say`-generated clip through the proxy

**Issues**:
- Notifications don't show, so errors are invisible. Proposed: error sound + ⚠️ icon + log file

---

### 2026-09-25
**Session**: Scoping + implementation
**Done**:
- Brainstormed hotkey options; user chose Right Option (transcribe) / Right Command (Claude)
- Implemented all requirements above
- Scripted behavioral tests (39 checks, all passing): taps, holds, combos before/after the hold delay, twin-modifier quirk, injected events, silence, short clips, busy guard, Claude mode, mic failure recovery, callback exception containment, clipboard snapshot/restore on a private pasteboard (multi-type, changed-meanwhile, paste failure, empty)
- Smoke-launched the real rumps app: `callAfter` dispatches to the main thread, listener stays alive

**State at end**:
- Committed and pushed. Needs real-world use with a real mic/keyboard

**Issues**:
- Couldn't test physical key presses or real mic levels from the Claude Code shell (no Accessibility permission there)

---

## Current State
<!-- THIS IS THE MOST IMPORTANT SECTION FOR SESSION HANDOFF -->

**What's done**:
- Everything in Requirements, pushed to `main`

**What's in progress**:
- Real-world testing by the user

**What's NOT working**:
- Error notifications don't appear, so failures look silent (see Next Steps). Watch for: silence threshold too aggressive on quiet mics (lower `SILENCE_THRESHOLD`), clipboard restore racing slow apps (raise `CLIPBOARD_RESTORE_DELAY`)

## Next Steps
<!-- Ordered by priority. Check off as you complete. -->
1. [ ] Use it for a few days; confirm Right Option/Command feel right and nothing fires by accident
2. [ ] Make errors visible: Basso sound + ⚠️ icon + `~/Library/Logs/voice-terminal.log`
3. [ ] Tune `SILENCE_THRESHOLD` / `CLIPBOARD_RESTORE_DELAY` if needed
4. [ ] Move this plan to `archive/`

## Future (out of scope here)
- Fn/Globe hold-to-talk via a Quartz event tap
- Job queue / multi-window targeting (see `queue-architecture.md`); the busy guard is the stand-in
- Claude mode: newer model default, terminal-safe multi-line paste, streaming
- "…and submit" voice command, history menu, local Whisper

## Testing Notes
**Local testing**:
```bash
source venv/bin/activate && python overtone.py
# Transcribe: focus a text field, hold Right Option, wait for Tink, speak, release
# Tap Right Option quickly: nothing should happen
# Option+Left (right Option) in an editor: cursor jumps a word, no recording
# Copy something, dictate, then Cmd+V: original copy comes back
# Hold Right Option ~1s without speaking: "No speech detected", nothing pasted
# Dictate, then immediately hold Right Option again: Funk sound
# Claude: copy code, hold Right Command, "explain this", release
```

## Completion Criteria
<!-- All must be checked before moving to archive -->
- [x] Feature works as specified (scripted tests)
- [ ] Confirmed in real usage
- [x] Code is clean and follows conventions
- [ ] No regressions introduced (confirm in real usage)
