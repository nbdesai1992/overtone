#!/usr/bin/env python3
"""
Voice Terminal - A macOS menubar app for voice-to-text in any application.

Mode 1: Hold Right Option to transcribe speech directly.
Mode 2: Hold Right Command to send clipboard + speech to Claude, paste response.
"""

import io
import os
import subprocess
import tempfile
import threading
import time
import wave

import numpy as np
import rumps
import sounddevice as sd
from AppKit import NSData, NSPasteboard, NSPasteboardItem, NSPasteboardTypeString
from dotenv import load_dotenv
from openai import OpenAI
from pynput import keyboard
from PyObjCTools import AppHelper

# Marks our temporary clipboard contents so clipboard managers ignore them (nspasteboard.org)
TRANSIENT_PASTEBOARD_TYPE = "org.nspasteboard.TransientType"


def play_sound(sound_name):
    """Play a macOS system sound."""
    sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
    subprocess.Popen(["afplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def on_main_thread(func, *args, **kwargs):
    """Run func on the main thread. AppKit UI (menubar, notifications) is not thread-safe."""
    AppHelper.callAfter(func, *args, **kwargs)


def notify(subtitle, message):
    """Show a notification. Safe to call from any thread."""
    on_main_thread(rumps.notification, title="Voice Terminal", subtitle=subtitle, message=message)


def get_clipboard():
    """Read current clipboard text."""
    return NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString) or ""


def snapshot_clipboard():
    """Capture every item and data type on the clipboard (text, images, files, rich text)."""
    snapshot = []
    for item in NSPasteboard.generalPasteboard().pasteboardItems() or []:
        item_data = {}
        for data_type in item.types():
            data = item.dataForType_(data_type)
            if data is not None:
                item_data[data_type] = data
        snapshot.append(item_data)
    return snapshot


def restore_clipboard(snapshot):
    """Put a snapshot from snapshot_clipboard() back on the clipboard."""
    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    items = []
    for item_data in snapshot:
        item = NSPasteboardItem.alloc().init()
        for data_type, data in item_data.items():
            item.setData_forType_(data, data_type)
        items.append(item)
    if items:
        pasteboard.writeObjects_(items)


def paste_text(text):
    """Paste text into the focused app, then restore the user's clipboard."""
    pasteboard = NSPasteboard.generalPasteboard()
    saved = snapshot_clipboard()

    pasteboard.declareTypes_owner_([NSPasteboardTypeString, TRANSIENT_PASTEBOARD_TYPE], None)
    pasteboard.setString_forType_(text, NSPasteboardTypeString)
    pasteboard.setData_forType_(NSData.data(), TRANSIENT_PASTEBOARD_TYPE)
    our_change_count = pasteboard.changeCount()

    # If this fails we skip the restore, leaving the text on the clipboard to paste manually
    subprocess.run([
        'osascript', '-e',
        'tell application "System Events" to keystroke "v" using command down'
    ], check=True)

    # The target app reads the clipboard asynchronously, so wait before restoring.
    # Skip the restore if something else was copied in the meantime.
    time.sleep(CLIPBOARD_RESTORE_DELAY)
    if pasteboard.changeCount() == our_change_count:
        restore_clipboard(saved)


def is_silent(audio):
    """True if no 50ms window of audio is louder than SILENCE_THRESHOLD (RMS)."""
    window = SAMPLE_RATE // 20
    usable = len(audio) - len(audio) % window
    if usable == 0:
        return True
    windows = audio[:usable].reshape(-1, window)
    loudest = np.sqrt(np.mean(windows ** 2, axis=1)).max()
    return loudest < SILENCE_THRESHOLD


def close_stream(stream):
    """Stop and close an audio stream, ignoring errors."""
    if stream is None:
        return
    try:
        stream.stop()
        stream.close()
    except Exception:
        pass


# Load environment variables from .env file
load_dotenv()

# Configuration
# Hold-to-talk hotkeys. Modifier-only keys send nothing to the focused app, so
# holding them can't trigger app shortcuts (Cmd+Shift+Z was Redo everywhere).
HOTKEYS = {
    keyboard.Key.alt_r: 'transcribe',  # Right Option
    keyboard.Key.cmd_r: 'claude',      # Right Command
}
HOLD_DELAY = 0.15  # Seconds to hold before recording starts, so quick taps do nothing
MIN_RECORDING_SECONDS = 0.3  # Shorter clips are accidental taps (Whisper rejects them anyway)
SILENCE_THRESHOLD = float(os.environ.get("SILENCE_THRESHOLD", "0.005"))  # RMS; lower = more sensitive
CLIPBOARD_RESTORE_DELAY = 0.5  # Seconds to wait after pasting before restoring the clipboard
TRANSCRIBE_MODEL = os.environ.get("TRANSCRIBE_MODEL", "whisper-1")
# Optional value for the API's `user` field on every request. Some proxies (e.g. LiteLLM)
# use it for project attribution.
API_USER = os.environ.get("API_USER")
API_EXTRA_BODY = {"user": API_USER} if API_USER else None
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1


class VoiceTerminalApp(rumps.App):
    def __init__(self):
        super().__init__("Voice Terminal", icon=None, title="🎤")

        # State, shared by the key listener, hold timer, and worker threads.
        # Guarded by self.lock.
        self.lock = threading.Lock()
        self.state = 'idle'  # 'idle', 'recording', or 'processing'
        self.held_hotkey = None  # Hotkey currently held down
        self.hotkey_combo = False  # Another key was pressed while holding the hotkey
        self.hold_timer = None
        self.stream = None
        self.audio_chunks = []
        self.current_mode = None  # 'transcribe' or 'claude'
        self.clipboard_context = None  # Stored clipboard for claude mode

        # Transcription client (Whisper). Any OpenAI-compatible endpoint; defaults to OpenAI.
        api_key = os.environ.get("TRANSCRIBE_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            rumps.alert(
                title="API Key Missing",
                message="Please set OPENAI_API_KEY (or TRANSCRIBE_API_KEY) in .env."
            )
        transcribe_base_url = os.environ.get("TRANSCRIBE_BASE_URL")  # None = OpenAI
        self.whisper_client = OpenAI(api_key=api_key, base_url=transcribe_base_url) if api_key else None

        # LLM client (for Claude mode)
        llm_api_key = os.environ.get("LLM_API_KEY")
        llm_base_url = os.environ.get("LLM_BASE_URL")
        self.llm_model = os.environ.get("LLM_MODEL", "claude-opus-4-5-20250514")

        if llm_api_key and llm_base_url and llm_api_key != "your-llm-api-key-here":
            self.llm_client = OpenAI(api_key=llm_api_key, base_url=llm_base_url)
        else:
            self.llm_client = None

        # Menu items
        self.status_item = rumps.MenuItem("Status: Ready", callback=None)
        self.menu = [
            self.status_item,
            None,  # Separator
            rumps.MenuItem("Hold Right Option: Transcribe", callback=None),
            rumps.MenuItem("Hold Right Command: Ask Claude", callback=None),
            None,
        ]

        # Start hotkey listener
        self.listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self.listener.start()

    # Key handling. These run on the listener thread: keep them fast, and never
    # let an exception escape, because that stops the listener for good.

    def on_key_press(self, key, injected):
        """Handle key press events."""
        if injected:
            return  # Synthetic events, like our own Cmd+V
        try:
            with self.lock:
                if key == self.held_hotkey:
                    # Modifiers don't auto-repeat, so a second press means the hotkey was
                    # released while its twin (e.g. Left Option) was still down
                    self._hotkey_released()
                elif self.held_hotkey is not None:
                    # Another key while holding the hotkey: it's a shortcut
                    # (Option+Left, Cmd+C...), not dictation
                    self.hotkey_combo = True
                    self._cancel_hold_timer()
                    if self.state == 'recording':
                        self._cancel_recording()
                elif key in HOTKEYS:
                    self.held_hotkey = key
                    self.hotkey_combo = False
                    self.hold_timer = threading.Timer(HOLD_DELAY, self._on_hotkey_held, args=(key,))
                    self.hold_timer.daemon = True
                    self.hold_timer.start()
        except Exception as e:
            notify("Error", str(e)[:100])

    def on_key_release(self, key, injected):
        """Handle key release events."""
        if injected:
            return
        try:
            with self.lock:
                if key == self.held_hotkey:
                    self._hotkey_released()
        except Exception as e:
            notify("Error", str(e)[:100])

    def _on_hotkey_held(self, key):
        """Hold timer fired: the hotkey is being held on its own, so start recording."""
        try:
            with self.lock:
                if self.held_hotkey != key or self.hotkey_combo:
                    return
                if self.state != 'idle':
                    play_sound("Funk")  # Still processing the previous recording
                    return
                self._start_recording(HOTKEYS[key])
        except Exception as e:
            notify("Error", str(e)[:100])

    def _hotkey_released(self):
        """Hotkey let go: finish the recording, if one is running. Call with lock held."""
        self.held_hotkey = None
        self._cancel_hold_timer()
        if self.state == 'recording':
            self._stop_recording()

    def _cancel_hold_timer(self):
        if self.hold_timer:
            self.hold_timer.cancel()
            self.hold_timer = None

    # Recording. Call these with the lock held.

    def _start_recording(self, mode):
        """Start recording audio."""
        if not self.whisper_client:
            notify("Error", "OpenAI API key not configured")
            return

        if mode == 'claude' and not self.llm_client:
            notify("Error", "LLM API not configured. Set LLM_API_KEY and LLM_BASE_URL in .env")
            return

        self.current_mode = mode
        # Capture clipboard before recording
        self.clipboard_context = get_clipboard() if mode == 'claude' else None

        # Start audio stream
        chunks = []

        def audio_callback(indata, frames, time_info, status):
            chunks.append(indata.copy())

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.float32,
            callback=audio_callback
        )
        try:
            stream.start()
        except Exception:
            stream.close()
            raise

        self.stream = stream
        self.audio_chunks = chunks
        self.state = 'recording'

        # Audio feedback - recording started
        play_sound("Tink")

        # Different visual feedback per mode
        if mode == 'transcribe':
            on_main_thread(self.show_status, "🔴", "Status: Recording...")
            notify("Recording", "Speak now... Release Right Option when done.")
        else:  # claude mode
            on_main_thread(self.show_status, "🟣", "Status: Recording (Claude)...")
            context = self.clipboard_context
            context_preview = context[:30] + "..." if len(context) > 30 else context
            notify("Recording (Claude Mode)", f"Context: {context_preview or '(empty)'}")

    def _stop_recording(self):
        """Stop recording and process audio in the background."""
        self.state = 'processing'
        stream, self.stream = self.stream, None
        chunks, self.audio_chunks = self.audio_chunks, []

        # Different visual feedback per mode
        if self.current_mode == 'transcribe':
            on_main_thread(self.show_status, "⏳", "Status: Transcribing...")
        else:
            on_main_thread(self.show_status, "🤖", "Status: Asking Claude...")

        # Audio feedback - recording stopped
        play_sound("Pop")

        # Process in background thread to not block the key listener
        threading.Thread(
            target=self.process_audio,
            args=(stream, chunks, self.current_mode, self.clipboard_context),
            daemon=True
        ).start()

    def _cancel_recording(self):
        """Discard the current recording without transcribing it."""
        stream, self.stream = self.stream, None
        self.audio_chunks = []
        self.state = 'idle'
        self.current_mode = None
        self.clipboard_context = None
        threading.Thread(target=close_stream, args=(stream,), daemon=True).start()
        on_main_thread(self.reset_status)

    def process_audio(self, stream, chunks, mode, clipboard_context):
        """Process recorded audio: transcribe and optionally send to Claude."""
        try:
            close_stream(stream)

            if not chunks:
                return

            # Combine audio chunks
            audio = np.concatenate(chunks).flatten()

            # Skip accidental taps
            if len(audio) < MIN_RECORDING_SECONDS * SAMPLE_RATE:
                return

            # Skip silence: Whisper invents text like "Thank you." from it
            if is_silent(audio):
                notify("No Speech", "No speech detected")
                return

            # Convert to WAV format for Whisper API
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(SAMPLE_RATE)
                # Convert float32 to int16, clipping so loud input doesn't wrap around
                audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())

            wav_buffer.seek(0)

            # Create a temporary file for the API
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(wav_buffer.read())
                tmp_path = tmp.name

            try:
                # Transcribe with Whisper
                with open(tmp_path, "rb") as audio_file:
                    # JSON (the default) rather than "text": some proxies return JSON either way
                    transcript = self.whisper_client.audio.transcriptions.create(
                        model=TRANSCRIBE_MODEL,
                        file=audio_file,
                        extra_body=API_EXTRA_BODY
                    )

                text = transcript.text.strip()

                if text:
                    if mode == 'transcribe':
                        # Mode 1: Direct transcription
                        paste_text(text)
                        notify("Typed", text[:50] + "..." if len(text) > 50 else text)
                    else:
                        # Mode 2: Send to Claude
                        response = self.call_llm(clipboard_context, text)
                        paste_text(response)
                        notify("Claude Response", response[:50] + "..." if len(response) > 50 else response)
                else:
                    notify("No Speech", "No speech detected")
            finally:
                # Clean up temp file
                os.unlink(tmp_path)

        except Exception as e:
            notify("Error", str(e)[:100])

        finally:
            with self.lock:
                self.state = 'idle'
                self.current_mode = None
                self.clipboard_context = None
            on_main_thread(self.reset_status)

    def call_llm(self, context: str, prompt: str) -> str:
        """Send context + prompt to Claude and return response."""
        if context:
            user_message = f"Context:\n```\n{context}\n```\n\nRequest: {prompt}"
        else:
            user_message = prompt

        response = self.llm_client.chat.completions.create(
            model=self.llm_model,
            max_tokens=4096,
            extra_body=API_EXTRA_BODY,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. The user may provide context (code, text, etc.) along with a spoken request. Respond concisely and directly - your response will be pasted into their editor or terminal."
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )
        return response.choices[0].message.content

    # UI updates. Main thread only: call through on_main_thread().

    def show_status(self, icon, status):
        """Update the menubar icon and status line."""
        self.title = icon
        self.status_item.title = status

    def reset_status(self):
        """Reset app status to ready state."""
        self.show_status("🎤", "Status: Ready")


if __name__ == "__main__":
    VoiceTerminalApp().run()
