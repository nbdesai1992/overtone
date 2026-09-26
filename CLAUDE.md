# Overtone

A voice-to-text tool for terminal/Claude Code. Speak commands, have them typed into the focused terminal window.

## Planning Paradigm

All feature work in this repository follows a structured planning process using the `.plans/` directory.

### Structure
```
.plans/
├── _template.md    # Copy this to start a new plan
├── active/         # Current work in progress
└── archive/        # Completed features (for reference)
```

### Workflow

1. **Starting a feature**: Copy `_template.md` to `active/feature-name.md`
2. **During work**: Update the plan's Progress Log and Current State sections after each session
3. **Completing a feature**: Move the plan from `active/` to `archive/`

### Why This Matters

- **Session continuity**: Claude Code sessions are stateless. The plan file IS the memory.
- **Handoff clarity**: The "Current State" section tells the next session exactly where to pick up.
- **Progress tracking**: The Progress Log shows what was done and when.

### Key Sections in Plans

- **Current State**: MOST IMPORTANT. Update this every time work stops. Be specific about what's done, in progress, and broken.
- **Next Steps**: Ordered task list. Check off as you go.
- **Progress Log**: Append-only history of work sessions.

## Tech Stack

- Python 3.9+
- Whisper API (OpenAI) for speech-to-text
- `pyautogui` for keystroke injection
- `rumps` for macOS menubar app
- `sounddevice` for audio capture
