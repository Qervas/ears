"""Live caption overlay UI using tkinter."""

import tkinter as tk
from tkinter import ttk
import threading
import queue
import time
from audio_capture import AudioCapture
from transcriber import Transcriber
from storage import save_transcript
from config import CHUNK_DURATION


class CaptionOverlay:
    """Floating caption window that shows live transcriptions."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EARS - Swedish Captions")

        # Make it a floating overlay
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)

        # Window size and position (bottom center of screen)
        window_width = 800
        window_height = 150
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = screen_height - window_height - 100
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Dark theme
        self.root.configure(bg='#1a1a1a')

        # Caption display
        self.caption_var = tk.StringVar(value="Starting...")
        self.caption_label = tk.Label(
            self.root,
            textvariable=self.caption_var,
            font=('Segoe UI', 18),
            fg='#ffffff',
            bg='#1a1a1a',
            wraplength=760,
            justify='center',
            pady=20
        )
        self.caption_label.pack(expand=True, fill='both')

        # Status bar
        self.status_frame = tk.Frame(self.root, bg='#2a2a2a')
        self.status_frame.pack(fill='x', side='bottom')

        self.status_var = tk.StringVar(value="Initializing...")
        self.status_label = tk.Label(
            self.status_frame,
            textvariable=self.status_var,
            font=('Segoe UI', 10),
            fg='#888888',
            bg='#2a2a2a',
            pady=5
        )
        self.status_label.pack(side='left', padx=10)

        # Segment counter
        self.count_var = tk.StringVar(value="Segments: 0")
        self.count_label = tk.Label(
            self.status_frame,
            textvariable=self.count_var,
            font=('Segoe UI', 10),
            fg='#888888',
            bg='#2a2a2a',
            pady=5
        )
        self.count_label.pack(side='right', padx=10)

        # Device selector button
        self.device_btn = tk.Button(
            self.status_frame,
            text="Select Device",
            command=self.show_device_selector,
            font=('Segoe UI', 9),
            bg='#3a3a3a',
            fg='#ffffff',
            relief='flat',
            padx=10
        )
        self.device_btn.pack(side='right', padx=5)

        # Caption history
        self.history = []
        self.max_history = 3

        # Queue for thread-safe updates
        self.update_queue = queue.Queue()

        # Components
        self.capture = None
        self.transcriber = None
        self.running = False
        self.segment_count = 0
        self.selected_device = None

        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start processing queue
        self.process_queue()

    def show_device_selector(self):
        """Show device selection dialog."""
        import sounddevice as sd

        dialog = tk.Toplevel(self.root)
        dialog.title("Select Audio Device")
        dialog.geometry("500x400")
        dialog.configure(bg='#1a1a1a')
        dialog.attributes('-topmost', True)
        dialog.transient(self.root)
        dialog.grab_set()

        # Label
        tk.Label(
            dialog,
            text="Select input device for system audio:",
            font=('Segoe UI', 12),
            fg='#ffffff',
            bg='#1a1a1a',
            pady=10
        ).pack()

        # Listbox with scrollbar
        frame = tk.Frame(dialog, bg='#1a1a1a')
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')

        listbox = tk.Listbox(
            frame,
            font=('Consolas', 10),
            bg='#2a2a2a',
            fg='#ffffff',
            selectbackground='#4a4a4a',
            yscrollcommand=scrollbar.set,
            height=15
        )
        listbox.pack(fill='both', expand=True)
        scrollbar.config(command=listbox.yview)

        # Populate devices
        devices = sd.query_devices()
        device_map = {}
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                name = f"[{i}] {dev['name']}"
                listbox.insert(tk.END, name)
                device_map[listbox.size() - 1] = i

        def on_select():
            selection = listbox.curselection()
            if selection:
                self.selected_device = device_map[selection[0]]
                dialog.destroy()
                self.restart_capture()

        tk.Button(
            dialog,
            text="Select",
            command=on_select,
            font=('Segoe UI', 11),
            bg='#4a4a4a',
            fg='#ffffff',
            relief='flat',
            padx=20,
            pady=5
        ).pack(pady=10)

    def restart_capture(self):
        """Restart capture with new device."""
        self.running = False
        time.sleep(0.5)
        if self.capture:
            self.capture.stop()
        self.start_capture_thread()

    def process_queue(self):
        """Process updates from the capture thread."""
        try:
            while True:
                msg_type, data = self.update_queue.get_nowait()
                if msg_type == 'caption':
                    self.update_caption(data)
                elif msg_type == 'status':
                    self.status_var.set(data)
                elif msg_type == 'count':
                    self.count_var.set(f"Segments: {data}")
        except queue.Empty:
            pass

        self.root.after(100, self.process_queue)

    def update_caption(self, text):
        """Update the caption display."""
        if not text or not text.strip():
            return

        self.history.append(text)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        # Show recent captions, newest at bottom and brighter
        display_lines = []
        for i, line in enumerate(self.history):
            display_lines.append(line)

        self.caption_var.set("\n".join(display_lines))

    def capture_loop(self):
        """Main capture and transcription loop."""
        self.update_queue.put(('status', 'Loading Whisper model...'))

        try:
            self.transcriber = Transcriber()
        except Exception as e:
            self.update_queue.put(('status', f'Error loading model: {e}'))
            return

        self.update_queue.put(('status', 'Starting audio capture...'))

        self.capture = AudioCapture(chunk_seconds=CHUNK_DURATION)

        device_id = self.selected_device
        if device_id is None:
            device_id = 14  # Default to Stereo Mix

        if not self.capture.start(device_id):
            self.update_queue.put(('status', 'Failed to start capture. Click "Select Device"'))
            return

        self.update_queue.put(('status', f'Listening on device {device_id}...'))
        self.running = True

        while self.running:
            try:
                if not self.capture.has_audio():
                    time.sleep(0.1)
                    continue

                audio = self.capture.get_chunk()
                if audio is None:
                    continue

                self.update_queue.put(('status', 'Transcribing...'))
                text, confidence = self.transcriber.transcribe(audio)

                if text and text.strip():
                    # Save to database
                    save_transcript(
                        raw_text=text,
                        confidence=confidence,
                        duration=CHUNK_DURATION
                    )
                    self.segment_count += 1

                    self.update_queue.put(('caption', text))
                    self.update_queue.put(('count', self.segment_count))

                self.update_queue.put(('status', f'Listening on device {device_id}...'))

            except Exception as e:
                self.update_queue.put(('status', f'Error: {e}'))
                time.sleep(1)

        if self.capture:
            self.capture.stop()

    def start_capture_thread(self):
        """Start the capture thread."""
        thread = threading.Thread(target=self.capture_loop, daemon=True)
        thread.start()

    def on_close(self):
        """Handle window close."""
        self.running = False
        time.sleep(0.3)
        self.root.destroy()

    def run(self):
        """Start the UI."""
        self.start_capture_thread()
        self.root.mainloop()


def main():
    app = CaptionOverlay()
    app.run()


if __name__ == "__main__":
    main()
