# Feature: Claude Voice Assistant Mode

## Metadata
- **Status**: `testing`
- **Created**: 2025-01-30
- **Last Updated**: 2025-01-30
- **Priority**: `high`

## Overview
Add a second hotkey that sends clipboard context + spoken prompt to Claude Opus 4.5 and pastes the response. This transforms Overtone from a transcription tool into a voice-activated AI assistant that can see what you've copied.

**Use case**: Copy some code → press hotkey → say "explain this" or "refactor to use async" → Claude's response appears in your focused window.

## Requirements
- [ ] Second hotkey (e.g., Cmd+Shift+A) triggers "Claude mode"
- [ ] Read clipboard contents on hotkey press
- [ ] Record and transcribe speech (existing Whisper flow)
- [ ] Send clipboard + transcription to Claude Opus 4.5
- [ ] Paste Claude's response into focused window
- [ ] Visual/audio feedback distinguishing modes
- [ ] ANTHROPIC_API_KEY support in .env

## Technical Approach

### Architecture

```
Mode 1 (existing): Cmd+Shift+Z
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Record      │───▶│ Whisper     │───▶│ Paste       │
│ Audio       │    │ Transcribe  │    │ Text        │
└─────────────┘    └─────────────┘    └─────────────┘

Mode 2 (new): Cmd+Shift+A
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Read        │───▶│ Record      │───▶│ Whisper     │───▶│ Claude      │
│ Clipboard   │    │ Audio       │    │ Transcribe  │    │ Opus 4.5    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                │
                                                                ▼
                                                         ┌─────────────┐
                                                         │ Paste       │
                                                         │ Response    │
                                                         └─────────────┘
```

### Key Implementation Details

**1. Hotkey Detection**
```python
HOTKEY_TRANSCRIBE = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('z')}
HOTKEY_CLAUDE = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('a')}

# Track which mode was triggered
self.current_mode = None  # 'transcribe' or 'claude'
```

**2. Clipboard Reading (macOS)**
```python
def get_clipboard():
    result = subprocess.run(['pbpaste'], capture_output=True, text=True)
    return result.stdout
```

**3. Claude API Call**
```python
from anthropic import Anthropic

self.anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def call_claude(self, clipboard_context: str, spoken_prompt: str) -> str:
    messages = [
        {
            "role": "user",
            "content": f"Context:\n```\n{clipboard_context}\n```\n\nRequest: {spoken_prompt}"
        }
    ]

    response = self.anthropic_client.messages.create(
        model="claude-opus-4-5-20250514",
        max_tokens=4096,
        messages=messages
    )
    return response.content[0].text
```

**4. Prompt Construction Options**

Option A: Simple concatenation
```
Context:
```
{clipboard}
```

Request: {spoken_prompt}
```

Option B: System prompt for behavior
```python
system = "You are a helpful assistant. The user will provide context (usually code or text they copied) and a spoken request. Respond concisely and directly - your response will be pasted into their editor."
```

Option C: Smart context detection
- Detect if clipboard looks like code (has indentation, keywords)
- Adjust system prompt accordingly

**Recommendation**: Start with Option A, iterate based on usage.

**5. UI Feedback**

| Mode | Icon During Recording | Icon During Processing |
|------|----------------------|------------------------|
| Transcribe | 🔴 | ⏳ |
| Claude | 🟣 (or 🔵) | 🤖 |

Different sounds could also help distinguish modes.

**6. Response Handling**

Claude responses may be multi-line. Current paste mechanism should handle this fine since we're using clipboard + Cmd+V.

Consider: Should we strip markdown formatting? Or keep it? Probably keep it - user can ask for "plain text" if needed.

### Files to Modify/Create
| File | Action | Description |
|------|--------|-------------|
| `overtone.py` | modify | Add second hotkey, Claude API integration, mode tracking |
| `.env.example` | create | Document required environment variables |
| `requirements.txt` | modify | Add `anthropic` package |
| `README.md` | modify | Document new hotkey and setup |

### Dependencies
```
anthropic>=0.40.0  # Claude API SDK
```

## Progress Log
<!-- Append new entries at the top. This is the session continuity record. -->

### 2025-01-30
**Session**: Initial planning
**Done**:
- Defined requirements
- Designed architecture
- Documented implementation approach

**State at end**:
- Plan complete, ready for implementation

**Issues**:
- None yet

---

## Current State
<!-- THIS IS THE MOST IMPORTANT SECTION FOR SESSION HANDOFF -->

**What's done**:
- Plan document created
- Architecture designed
- Implementation complete
- Two hotkeys: Cmd+Shift+Z (transcribe), Cmd+Shift+A (Claude)
- Clipboard context captured on Claude mode activation
- LLM client uses OpenAI-compatible API with custom base URL
- Visual feedback: 🔴 for transcribe, 🟣 for Claude, 🤖 for waiting on Claude
- README updated with new documentation

**What's in progress**:
- User testing - needs LLM_API_KEY and LLM_BASE_URL configured

**What's NOT working**:
- N/A - awaiting user to add API credentials and test

## Next Steps
<!-- Ordered by priority. Check off as you complete. -->
1. [ ] Add ANTHROPIC_API_KEY to .env
2. [ ] Add `anthropic` to requirements.txt
3. [ ] Refactor hotkey detection to support multiple hotkeys
4. [ ] Add mode tracking (self.current_mode)
5. [ ] Implement clipboard reading
6. [ ] Add Anthropic client initialization
7. [ ] Implement call_claude() method
8. [ ] Modify process_audio() to branch based on mode
9. [ ] Add distinct UI feedback for Claude mode
10. [ ] Test end-to-end
11. [ ] Update README with new hotkey documentation

## Blockers
<!-- Remove when resolved. Add resolution notes. -->
- [ ] Need ANTHROPIC_API_KEY added to .env before testing

## Open Questions
<!-- Decisions that need to be made -->
- [ ] Hotkey for Claude mode: Cmd+Shift+A? Something else?
- [ ] Should clipboard context be optional? (proceed with just voice if clipboard empty)
- [ ] Max response length from Claude? (affects latency)
- [ ] Should we add a system prompt to guide Claude's response style?

## Testing Notes
**Local testing**:
```bash
# 1. Add API key
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# 2. Install new dependency
pip install anthropic

# 3. Run app
python overtone.py

# 4. Test Mode 1 (should work as before)
# - Focus a text field, Cmd+Shift+Z, speak, release

# 5. Test Mode 2
# - Copy some code
# - Focus a text field
# - Cmd+Shift+A, say "explain this", release
# - Claude's explanation should appear
```

## Completion Criteria
<!-- All must be checked before moving to archive -->
- [ ] Mode 1 (transcribe) works as before - no regression
- [ ] Mode 2 (Claude) reads clipboard and spoken prompt
- [ ] Mode 2 sends to Claude Opus 4.5 and pastes response
- [ ] Visual feedback distinguishes the two modes
- [ ] README documents new feature
- [ ] Works reliably for 10+ consecutive uses without crash
