# 🖤 SpeedReader — Lightning-Fast PDF RSVP (Dark Edition)

A minimalist **speed-reading app for PDFs** built in Python with `tkinter`.  
It streams your text **one word at a time (RSVP)** in a sleek dark interface — clean, fast, and focused.

---

## 🚀 Features

- 🧠 **Smart PDF text extraction** — cleans line breaks, hyphenation, and extra spaces  
- ⚡ **RSVP engine** — reads at 100–1200 WPM with punctuation-aware timing  
- 🌙 **Dark mode UI** — optimized for comfort and long reading sessions  
- 💾 **Session persistence** — automatically remembers your position and last WPM  
- ⏱️ **Live stats** — shows progress, percentage, and time remaining  
- ⌨️ **Keyboard shortcuts** —  
  - `Space` → Pause / Resume  
  - `Esc` → Stop  
- 🔒 **Offline & private** — no network connections; all data stored locally

---

## 🧩 How It Works

1. The app extracts text from your PDF using `PyPDF2`.  
2. It cleans and tokenizes the content into words.  
3. Each word is displayed at your chosen **WPM rate** using RSVP timing logic.  
4. Punctuation automatically adds short pauses for natural rhythm.  
5. Your reading position and speed are saved in a local `.speedreader_state.json` file.

---

## 💡 Why It’s Effective

- **RSVP (Rapid Serial Visual Presentation)** minimizes eye movement and increases focus.  
- **Punctuation-aware delays** preserve the natural flow of language.  
- **Distraction-free UI** keeps attention centered on comprehension.  

---

## 🛠️ Requirements

- Python **3.8+**  
- `PyPDF2` → `pip install PyPDF2`  
- `tkinter` → comes preinstalled with most Python distributions

---

## ▶️ Quick Start

```bash
# 1. Install dependency
pip install PyPDF2

# 2. Run the program
python speedreader.py
