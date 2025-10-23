from pathlib import Path
import os
import json
import hashlib
import re
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --- PDF backend ---
try:
    import PyPDF2
    PDF_BACKEND = "PyPDF2"
except Exception:
    PyPDF2 = None
    PDF_BACKEND = None

APP_STATE_PATH = os.path.join(Path.home(), ".speedreader_state.json")

def load_state():
    if os.path.exists(APP_STATE_PATH):
        try:
            with open(APP_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    try:
        with open(APP_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        # Fallback – zapisz w katalogu roboczym
        fallback = os.path.join(os.getcwd(), ".speedreader_state.json")
        with open(fallback, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

def pdf_to_text(filepath: str) -> str:
    if PDF_BACKEND != "PyPDF2" or PyPDF2 is None:
        raise RuntimeError("Brak PyPDF2. Zainstaluj: pip install PyPDF2")
    text_chunks = []
    with open(filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            pg_text = page.extract_text() or ""
            text_chunks.append(pg_text)
    raw = "\n".join(text_chunks)

    # Czyszczenie
    cleaned = re.sub(r"(\w)-\n(\w)", r"\1\2", raw)    # "szyb-\nkiego" -> "szybkiego"
    cleaned = re.sub(r"\s*\n\s*", " ", cleaned)       # nowe linie -> spacja
    cleaned = re.sub(r"[ \t\u00A0]+", " ", cleaned)   # wielokrotne spacje -> jedna
    cleaned = cleaned.strip()
    return cleaned

def text_fingerprint(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def split_into_words(text: str):
    rough = re.findall(r"\S+", text)
    tokens = []
    for tok in rough:
        parts = re.split(r"([—–:;])", tok)
        for p in parts:
            if p:
                tokens.append(p)
    return tokens

def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:d}h {m:02d}m {s:02d}s"
    else:
        return f"{m:d}m {s:02d}s"

class SpeedReaderApp:
    def __init__(self, root):
        self.root = root
        root.title("Szybkie czytanie – PDF RSVP (Dark)")
        root.geometry("1000x560")
        root.minsize(800, 460)

        # DARK THEME COLORS
        self.bg = "#000000"
        self.fg = "#FFFFFF"
        self.bg2 = "#111111"
        self.accent = "#2E7D32"  # used for progressbar fill

        self.state = load_state()

        self.words = []
        self.word_index = 0
        self.wpm_var = tk.IntVar(value=400)
        self.is_running = False
        self.after_id = None
        self.current_fingerprint = None
        self.current_file = None

        # --- Window background
        root.configure(bg=self.bg)

        # --- ttk Styles for dark mode
        style = ttk.Style()
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        style.configure("Dark.TFrame", background=self.bg)
        style.configure("Dark.TLabel", background=self.bg, foreground=self.fg)
        style.configure("Dark.TButton", background=self.bg2, foreground=self.fg, relief="flat")
        style.map("Dark.TButton",
                  background=[("active", "#1c1c1c")],
                  foreground=[("disabled", "#666666")])
        style.configure("Dark.Horizontal.TProgressbar", background=self.accent, troughcolor="#222222")

        # --- TOP BAR
        top = ttk.Frame(root, padding=12, style="Dark.TFrame")
        top.pack(fill="x")

        self.open_btn = ttk.Button(top, text="Otwórz PDF…", command=self.open_pdf, style="Dark.TButton")
        self.open_btn.pack(side="left")

        wpm_label = ttk.Label(top, text="Tempo (słów/min):", style="Dark.TLabel")
        wpm_label.pack(side="left", padx=(12, 4))
        # Use tk.Spinbox to easily color it
        self.wpm_spin = tk.Spinbox(top, from_=100, to=1200, increment=50, textvariable=self.wpm_var, width=8,
                                   bg=self.bg2, fg=self.fg, insertbackground=self.fg, relief="flat")
        self.wpm_spin.pack(side="left")

        self.start_btn = ttk.Button(top, text="Start", command=self.start, style="Dark.TButton")
        self.start_btn.pack(side="left", padx=(12, 4))

        self.pause_btn = ttk.Button(top, text="Pauza (Spacja)", command=self.toggle_pause,
                                    state="disabled", style="Dark.TButton")
        self.pause_btn.pack(side="left", padx=4)

        self.stop_btn = ttk.Button(top, text="Stop", command=self.stop,
                                   state="disabled", style="Dark.TButton")
        self.stop_btn.pack(side="left", padx=4)

        # STATUS BAR
        self.status_var = tk.StringVar(value="Otwórz plik PDF, ustaw tempo i wciśnij Start.")
        self.status_lbl = ttk.Label(root, textvariable=self.status_var, anchor="w", style="Dark.TLabel")
        self.status_lbl.pack(fill="x", padx=12)

        # PROGRESSBAR
        self.progress = ttk.Progressbar(root, orient="horizontal", mode="determinate",
                                        style="Dark.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=12, pady=(0, 4))

        # ETA + PERCENT
        self.meta_var = tk.StringVar(value="Pozostało: — | Postęp: —")
        self.meta_lbl = ttk.Label(root, textvariable=self.meta_var, anchor="e", style="Dark.TLabel")
        self.meta_lbl.pack(fill="x", padx=12, pady=(0, 6))

        # MAIN WORD DISPLAY
        self.display = tk.Label(
            root, text="", font=("Helvetica", 64, "bold"),
            wraplength=920, justify="center", anchor="center",
            bg=self.bg, fg=self.fg
        )
        self.display.pack(expand=True, fill="both", padx=12, pady=12)

        # Bindings
        root.bind("<space>", self.on_space)
        root.bind("<Escape>", self.on_escape)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # When WPM changes, update ETA immediately
        self.wpm_spin.bind("<KeyRelease>", lambda e: self.update_meta())
        self.wpm_spin.bind("<ButtonRelease-1>", lambda e: self.update_meta())

    # --- File & state ---
    def open_pdf(self):
        path = filedialog.askopenfilename(title="Wybierz plik PDF", filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        try:
            text = pdf_to_text(path)
            if not text:
                messagebox.showerror("Błąd", "Nie udało się odczytać tekstu z PDF.")
                return
            self.words = split_into_words(text)
            self.current_fingerprint = text_fingerprint(text)
            self.current_file = path
            total = len(self.words)
            self.progress.configure(maximum=max(1, total), value=0)

            last_pos = self.state.get("positions", {}).get(self.current_fingerprint, 0)
            self.word_index = max(0, min(last_pos, max(0, total - 1)))

            if self.word_index > 0:
                self.status_var.set(
                    f"Wczytano {os.path.basename(path)}. Wznowiono od słowa #{self.word_index+1}/{total}."
                )
                if self.words:
                    self.display.configure(text=self.words[self.word_index])
                self.progress.configure(value=self.word_index)
            else:
                self.status_var.set(f"Wczytano {os.path.basename(path)}. Gotowe do startu.")
                self.display.configure(text="")

            last_wpm = self.state.get("last_wpm")
            if last_wpm:
                self.wpm_var.set(int(last_wpm))

            self.pause_btn.config(state="normal")
            self.stop_btn.config(state="normal")

            self.update_meta()
        except Exception as e:
            messagebox.showerror("Błąd", f"Problem z odczytem PDF:\n{e}")

    def persist_position(self):
        if not self.current_fingerprint:
            return
        self.state.setdefault("positions", {})
        self.state["positions"][self.current_fingerprint] = int(self.word_index)
        self.state["last_wpm"] = int(self.wpm_var.get())
        save_state(self.state)

    # --- Controls ---
    def start(self):
        if not self.words:
            messagebox.showinfo("Brak pliku", "Najpierw wybierz plik PDF.")
            return
        if self.word_index >= len(self.words):
            self.word_index = 0

        self.is_running = True
        self.start_btn.config(state="disabled")
        self.pause_btn.config(text="Pauza (Spacja)", state="normal")
        self.stop_btn.config(state="normal")
        self.status_var.set("Czytanie… (Spacja = Pauza/Wznów, Esc = Stop)")
        self.schedule_next()

    def toggle_pause(self):
        if not self.words:
            return
        if self.is_running:
            self.is_running = False
            self.status_var.set("Wstrzymano. (Start lub Spacja = Wznów)")
            self.pause_btn.config(text="Wznów (Spacja)")
            self.cancel_scheduled()
            self.persist_position()
        else:
            self.is_running = True
            self.status_var.set("Czytanie… (Spacja = Pauza/Wznów, Esc = Stop)")
            self.pause_btn.config(text="Pauza (Spacja)")
            self.schedule_next()

    def stop(self):
        self.is_running = False
        self.cancel_scheduled()
        self.status_var.set("Zatrzymano. (Start = od bieżącego miejsca)")
        self.start_btn.config(state="normal")
        self.pause_btn.config(text="Pauza (Spacja)")
        self.persist_position()
        self.update_meta()

    # --- Reading loop ---
    def schedule_next(self):
        if not self.is_running:
            return
        if self.word_index >= len(self.words):
            self.finish_reading()
            return

        current_word = self.words[self.word_index]
        self.display.configure(text=current_word)

        self.word_index += 1
        self.update_meta()

        # Timing
        wpm = max(50, int(self.wpm_var.get()))
        base_delay_ms = int(60000 / wpm)
        if re.search(r"[.,;:!?…]$", current_word):
            delay = int(base_delay_ms * 1.7)
        elif re.search(r"[—–-]$", current_word):
            delay = int(base_delay_ms * 1.4)
        else:
            delay = base_delay_ms

        self.after_id = self.root.after(delay, self.schedule_next)

        # Save position occasionally
        if self.word_index % 50 == 0:
            self.persist_position()

    def update_meta(self):
        total = len(self.words)
        idx = min(self.word_index, total)
        self.progress.configure(maximum=max(1, total), value=idx)

        # Percent
        if total > 0:
            percent = idx / total * 100.0
            percent_str = f"{percent:.1f}%"
        else:
            percent_str = "—"

        # ETA: approximate using base WPM (ignoring punctuation pauses for simplicity)
        try:
            wpm = max(1, int(self.wpm_var.get()))
        except Exception:
            wpm = 400
        remaining_words = max(0, total - idx)
        secs_left = (remaining_words / float(wpm)) * 60.0
        eta_str = format_duration(secs_left) if total > 0 else "—"

        self.meta_var.set(f"Pozostało: {eta_str} | Postęp: {percent_str}")

    def finish_reading(self):
        self.is_running = False
        self.cancel_scheduled()
        self.status_var.set("Koniec pliku. (Start = od początku)")
        self.start_btn.config(state="normal")
        self.persist_position()
        self.update_meta()

    def cancel_scheduled(self):
        if hasattr(self, "after_id") and self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    # --- Bindings ---
    def on_space(self, event=None):
        if self.pause_btn["state"] != "disabled":
            self.toggle_pause()

    def on_escape(self, event=None):
        self.stop()

    def on_close(self):
        self.persist_position()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = SpeedReaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
