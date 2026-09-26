# Overtone

**Voice for Claude Code.** A macOS menubar app that lets you dictate text into any application. Hold a hotkey, speak, release - your words appear instantly.

Claude Code now has a built-in `/voice`. Overtone works in whichever window has focus, so one key serves every Claude Code session and terminal you have open, and a second key sends your clipboard plus a spoken question to Claude and pastes the answer.

Perfect for terminals, VS Code, Slack, or anywhere you want voice input.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/nbdesai1992/overtone.git
cd overtone
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add your OpenAI API key
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Run
python overtone.py
```

## How It Works

**Mode 1 - Transcribe (Right Option)**
1. Hold **Right Option** (⌥) and speak
2. Release the key
3. Your words appear in the focused window

**Mode 2 - Ask Claude (Right Command)**
1. Copy some text/code to clipboard
2. Hold **Right Command** (⌘) and speak your question
3. Release the key
4. Claude's response appears in the focused window

The app runs in your menubar and works with any application. Your clipboard is restored after each paste.

<!--
SCREENSHOT: Show the menubar with the 🎤 icon visible
Filename suggestion: screenshots/menubar-ready.png
-->

## Setup (Detailed)

### 1. Prerequisites

- macOS
- Python 3.9+
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))

### 2. Install

```bash
git clone https://github.com/nbdesai1992/overtone.git
cd overtone
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API Keys

Create a `.env` file in the project folder:

```bash
cat > .env << 'EOF'
# Required: OpenAI API key for Whisper transcription
OPENAI_API_KEY=sk-your-key-here

# Optional: LLM API for Claude mode (Right Command)
LLM_API_KEY=your-llm-api-key
LLM_BASE_URL=https://your-llm-endpoint.com/v1
LLM_MODEL=claude-opus-4-5-20250514
EOF
```

- **OPENAI_API_KEY**: Required for speech-to-text (Whisper)
- **LLM_*** variables: Optional, enables Claude mode for AI responses
- **TRANSCRIBE_API_KEY / TRANSCRIBE_BASE_URL / TRANSCRIBE_MODEL**: Optional. Send transcription to any OpenAI-compatible endpoint (e.g. a LiteLLM proxy) instead of OpenAI. Defaults: `OPENAI_API_KEY`, OpenAI, `whisper-1`
- **API_USER**: Optional. Sent as the `user` field on every API request (some proxies use it for project attribution)
- **SILENCE_THRESHOLD**: Optional (default `0.005`). Recordings quieter than this are skipped as silence. Lower it if quiet speech gets ignored

### 4. Grant Permissions

On first run, macOS will prompt for two permissions:

| Permission | Why It's Needed |
|------------|-----------------|
| **Microphone** | To record your voice |
| **Accessibility** | To paste text into other apps |

If you miss the prompts, go to **System Settings > Privacy & Security** and enable them manually for Terminal (or wherever you're running the script).

<!--
SCREENSHOT: System Settings > Privacy & Security > Accessibility with Terminal checked
Filename suggestion: screenshots/accessibility-permission.png
-->

### 5. Run

```bash
python overtone.py
```

The 🎤 icon appears in your menubar. You're ready to go.

## Usage

| Hotkey (hold) | Action |
|---------------|--------|
| **Right Option** | Transcribe speech → paste text |
| **Right Command** | Transcribe speech → send to Claude with clipboard context → paste response |

The hotkeys are modifier keys, so they never trigger app shortcuts. Quick taps and shortcuts that use them (like Option+← or Cmd+C) are ignored: pressing any other key while holding the hotkey cancels the recording.

| Menubar Icon | Status |
|--------------|--------|
| 🎤 | Ready |
| 🔴 | Recording (transcribe mode) |
| 🟣 | Recording (Claude mode) |
| ⏳ | Transcribing |
| 🤖 | Waiting for Claude |

<!--
SCREENSHOT: Animated GIF or side-by-side showing the states
Filename suggestion: screenshots/status-icons.gif
-->

**Audio feedback:**
- "Tink" sound when recording starts
- "Pop" sound when recording stops
- "Funk" sound if you hold the hotkey while the previous recording is still processing (wait for 🎤, then try again)

## Tips

- **Focus first**: Click on the target window before pressing the hotkey
- **Wait for the "Tink"**: Recording starts a moment after you press the key
- **Speak naturally**: Normal pace, clear pronunciation
- **Short phrases work best**: Whisper handles long dictation but shorter is snappier
- **Works everywhere**: Terminal, VS Code, Slack, browser text fields, etc.

## Cost

Uses OpenAI's Whisper API: **~$0.006 per minute** of audio.

A typical 5-second command costs about $0.0005 (fraction of a cent).

## Troubleshooting

### "API Key Missing" alert
- Make sure `.env` exists and contains your key
- Restart the app after creating/editing `.env`

### Hotkey does nothing
- Use the **right-hand** Option/Command keys; the left ones are left alone for normal shortcuts
- Check Accessibility permission in System Settings (it's needed to see key presses)
- Make sure you're not pressing other keys while holding the hotkey

### Text not appearing
- Check Accessibility permission in System Settings
- Make sure the target window is focused before pressing the hotkey
- Try a simple app like Notes first to verify it's working

### No audio captured
- Check Microphone permission in System Settings
- Test your mic in another app (Voice Memos, etc.)

### Wrong window receives text
- Click to focus your target window, then press the hotkey
- Don't switch windows while the ⏳ icon is showing

## Uninstall

Just delete the folder. The app doesn't install anything system-wide.

```bash
rm -rf overtone
```

Optionally revoke permissions in System Settings > Privacy & Security.
