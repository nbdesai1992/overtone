# Feature: Voice-to-Terminal

## Metadata
- **Status**: `complete`
- **Created**: 2025-01-16
- **Last Updated**: 2025-01-16
- **Priority**: `high`

## Overview
A macOS menubar utility that captures voice input via hotkey and types the transcribed text into the currently focused window. Enables voice control for terminals and any text input field, solving the problem that macOS dictation doesn't work in terminal apps.

## Requirements
- [x] Global hotkey to start/stop recording (Cmd+Shift+Z)
- [x] Audio capture from default microphone
- [x] Speech-to-text via Whisper API
- [x] Keystroke injection into focused window via pyautogui
- [x] macOS menubar icon for status/control
- [x] Audio feedback when recording starts/stops (Tink/Pop sounds)
- [x] .env file for API key management

## Technical Approach
Simple Python app using:
- `rumps` - macOS menubar app framework
- `sounddevice` - audio capture
- `numpy` - audio buffer handling
- `openai` - Whisper API for transcription
- `pyautogui` - keystroke injection
- `pynput` - global hotkey listener
- `python-dotenv` - environment variable management

### Architecture
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Hotkey    │────▶│   Record    │────▶│  Whisper    │
│  Listener   │     │   Audio     │     │    API      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  pyautogui  │
                                        │    type()   │
                                        └─────────────┘
```

### Files
| File | Description |
|------|-------------|
| `voice_terminal.py` | Main app - menubar, hotkey, recording, transcription, typing |
| `requirements.txt` | Python dependencies |
| `README.md` | Setup and usage instructions |
| `.env` | API key (gitignored) |
| `.gitignore` | Excludes .env, venv, pycache |

## Progress Log

### 2025-01-16 00:45
**Session**: Initial implementation and testing
**Done**:
- Created project structure and planning docs
- Built full voice_terminal.py with all functionality
- Added .env support for API key
- Set up Python 3.11 venv with all dependencies
- Added audio feedback (Tink/Pop sounds)
- Tested and working - transcription is fast and accurate
- Iterated on hotkey: Cmd+Shift+V → Option+Space → Option+` → Cmd+Shift+Z

**Issues**:
- Option+Space typed spaces into terminal (couldn't suppress)
- Settled on Cmd+Shift+Z which works well

---

## Current State

**Archived 2026-09-25**: in daily use since January. Hotkeys later moved to Right Option / Right Command (see `active/hotkey-and-reliability-fixes.md`); typing moved to clipboard paste.

**What's done**:
- Full working Mac app
- Hotkey: Cmd+Shift+Z (hold to record, release to transcribe)
- Audio feedback on start/stop
- Menubar icon shows status (🎤 ready, 🔴 recording, ⏳ processing)

**What's in progress**:
- User testing

**What's NOT working**:
- Nothing major - working well

## Next Steps
1. [ ] Continue testing with real usage
2. [ ] Consider toggle mode (press to start, press to stop) as alternative
3. [ ] Future: Windows support (would need pystray instead of rumps)

## Open Questions
- [ ] Should we add a "cancel" option if user starts recording by mistake?
- [ ] Toggle mode vs push-to-talk - which is preferred?

## Testing Notes
**Run the app**:
```bash
source "/Users/nealdesai/Library/Mobile Documents/com~apple~CloudDocs/Documents/CSProjects/voice-terminal/venv/bin/activate" && python "/Users/nealdesai/Library/Mobile Documents/com~apple~CloudDocs/Documents/CSProjects/voice-terminal/voice_terminal.py"
```

**Permissions needed**:
- System Preferences > Privacy & Security > Microphone
- System Preferences > Privacy & Security > Accessibility

## Completion Criteria
- [x] Hotkey triggers recording
- [x] Audio is captured and sent to Whisper
- [x] Transcribed text is typed into focused window
- [x] Menubar shows status
- [x] Works in VS Code terminal
- [ ] Tested thoroughly in real usage
