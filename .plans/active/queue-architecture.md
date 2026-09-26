# Queue Architecture for Multi-Window Dictation

## Status: Exploration
## Created: 2025-01-30
## Priority: Low (future consideration)

---

## Problem Statement

Currently, Overtone types text into whatever window has focus at the moment the transcription completes. This creates two limitations:

1. **Focus lock**: User must keep focus on target window while text types character-by-character
2. **No chaining**: Cannot dictate to Window A, switch to Window B, dictate again - the second transcription would go to B, but so would any remaining typing from the first

## Desired Behavior

User can:
1. Focus Terminal 1, dictate
2. Immediately focus Terminal 2, dictate
3. Immediately focus Terminal 3, dictate
4. All three transcriptions fill into their respective windows automatically

## Proposed Architecture

### Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Hotkey Press   │────▶│  Capture:       │────▶│  Recording      │
│  (Cmd+Shift+Z)  │     │  - Window ID    │     │  (Audio)        │
│                 │     │  - Timestamp    │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Type to        │◀────│  Job Queue      │◀────│  Whisper API    │
│  Target Window  │     │  (window, text) │     │  Transcription  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │
        ▼
┌─────────────────┐
│  Next Job       │
│  (if any)       │
└─────────────────┘
```

### Components

#### 1. Window Capture Service

When recording starts, capture the currently focused window:

```python
# macOS: Get frontmost window info via AppleScript
def get_focused_window():
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        set frontWindow to name of front window of first application process whose frontmost is true
    end tell
    return {frontApp, frontWindow}
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    # Parse result into (app_name, window_name)
    return parse_applescript_result(result.stdout)
```

**Stored data per recording:**
- `app_name`: e.g., "Terminal", "iTerm2", "Code"
- `window_identifier`: Window name or index
- `timestamp`: For ordering

#### 2. Job Queue

Simple in-memory queue (no cloud infrastructure needed):

```python
from dataclasses import dataclass
from queue import Queue
from threading import Thread

@dataclass
class TranscriptionJob:
    app_name: str
    window_id: str
    text: str
    timestamp: float

class JobQueue:
    def __init__(self):
        self.queue = Queue()
        self.worker = Thread(target=self._process_jobs, daemon=True)
        self.worker.start()

    def add(self, job: TranscriptionJob):
        self.queue.put(job)

    def _process_jobs(self):
        while True:
            job = self.queue.get()  # Blocks until job available
            self._type_to_window(job)
            self.queue.task_done()

    def _type_to_window(self, job: TranscriptionJob):
        # Activate target window, then type/paste
        activate_window(job.app_name, job.window_id)
        paste_text(job.text)
```

#### 3. Window Activation Service

Bring a specific window to focus before typing:

```python
def activate_window(app_name: str, window_id: str):
    """Activate a specific window using AppleScript."""
    script = f'''
    tell application "{app_name}"
        activate
        -- For apps with multiple windows, may need window index or name
    end tell
    '''
    subprocess.run(['osascript', '-e', script])
    time.sleep(0.1)  # Brief pause for window to come forward
```

**App-specific handling may be needed:**
- Terminal.app: `tell window 1 to activate`
- iTerm2: `tell current session of current window`
- VS Code: May need different approach (Electron app)

#### 4. Modified Recording Flow

```python
def start_recording(self):
    # Capture target window BEFORE recording starts
    self.target_window = get_focused_window()
    # ... existing recording logic ...

def process_audio(self):
    # ... existing Whisper transcription ...

    if text:
        job = TranscriptionJob(
            app_name=self.target_window.app_name,
            window_id=self.target_window.window_id,
            text=text,
            timestamp=time.time()
        )
        self.job_queue.add(job)
```

### Infrastructure Requirements

**This is entirely local - no cloud infrastructure needed.**

- All components run in the same Python process
- Queue is in-memory (stdlib `queue.Queue`)
- Worker thread processes jobs sequentially
- AppleScript handles window management (macOS native)

### Complexity Analysis

| Component | Complexity | Notes |
|-----------|------------|-------|
| Window capture | Low | Single AppleScript call |
| Job queue | Low | stdlib Queue + Thread |
| Window activation | Medium | App-specific edge cases |
| State management | Medium | Track pending jobs, handle errors |

**Total additional code:** ~100-150 lines

### Edge Cases to Handle

1. **Window closed**: Target window no longer exists when job processes
   - Solution: Show notification, skip job or type to current window

2. **App quit**: Target application was closed
   - Solution: Show notification with transcribed text (user can paste manually)

3. **Multiple windows same app**: "Terminal" has 3 windows, which one?
   - Solution: Capture window index or unique identifier, not just app name

4. **Rapid dictation**: Jobs backing up faster than typing
   - Solution: Use paste instead of character typing (already planned for v1)

5. **Focus race**: User switches window while activation happening
   - Solution: Brief mutex on window activation, or accept occasional misdirection

### Alternative: Simpler "Delayed Paste" Approach

If full window targeting is too complex, a simpler approach:

1. Queue transcriptions with their target window
2. When ready to type, show notification: "Ready to paste to Terminal 1 - press Cmd+Shift+P"
3. User manually focuses correct window and triggers paste

This is less automatic but much simpler to implement.

---

## Decision Log

- **2025-01-30**: Documented architecture for future reference. Current priority is clipboard+paste for instant typing. Queue architecture would be next evolution if chaining becomes a real need.

## Open Questions

1. How reliable is window identification across different apps?
2. Should we support cross-monitor scenarios?
3. Is there value in persisting the queue (survive app restart)?
4. Should completed transcriptions be logged/searchable?
