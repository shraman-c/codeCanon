import os
import re
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from pathlib import Path

# Root directory of the docs-drift-detector
ROOT_DIR = Path(__file__).resolve().parent.parent
DRIFT_SCRIPT = ROOT_DIR / "scripts" / "drift.py"

class DriftGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Docs-Drift-Detector GUI")
        self.geometry("900x700")
        self.configure(bg="#1e1e1e")
        
        # Variables
        self.target_dir = tk.StringVar()
        self.no_llm = tk.BooleanVar(value=False)
        self.no_images = tk.BooleanVar(value=False)
        
        self.create_widgets()
        self.setup_tags()

    def create_widgets(self):
        # Top Frame for controls
        control_frame = tk.Frame(self, padx=12, pady=10, bg="#25262b")
        control_frame.pack(fill=tk.X)
        
        # Directory Selection
        tk.Label(control_frame, text="Target Repository:", font=("Arial", 10, "bold"), bg="#25262b", fg="#ffffff").grid(row=0, column=0, sticky="w", pady=5)
        dir_entry = tk.Entry(control_frame, textvariable=self.target_dir, width=65, font=("Consolas", 10), bg="#2c2e33", fg="#ffffff", insertbackground="white")
        dir_entry.grid(row=0, column=1, padx=10)
        tk.Button(control_frame, text="Browse...", command=self.browse_dir, bg="#373a40", fg="#ffffff", activebackground="#495057").grid(row=0, column=2)
        
        # Flags
        options_frame = tk.Frame(control_frame, bg="#25262b")
        options_frame.grid(row=1, column=1, sticky="w", pady=5)
        tk.Checkbutton(options_frame, text="--no-llm (Fast deterministic mode)", variable=self.no_llm, bg="#25262b", fg="#cccccc", selectcolor="#1a1b1e", activebackground="#25262b").pack(side=tk.LEFT)
        tk.Checkbutton(options_frame, text="--no-images (Skip screenshots)", variable=self.no_images, bg="#25262b", fg="#cccccc", selectcolor="#1a1b1e", activebackground="#25262b").pack(side=tk.LEFT, padx=15)
        
        # Button frame
        btn_frame = tk.Frame(control_frame, bg="#25262b")
        btn_frame.grid(row=2, column=1, pady=8, sticky="w")
        
        self.run_btn = tk.Button(btn_frame, text="▶ Run Scan", command=self.start_scan, bg="#2b8a3e", fg="white", activebackground="#2f9e44", font=("Arial", 10, "bold"), width=14, relief=tk.FLAT)
        self.run_btn.pack(side=tk.LEFT)
        
        self.clear_btn = tk.Button(btn_frame, text="Clear Console", command=self.clear_output, bg="#373a40", fg="#cccccc", activebackground="#495057", font=("Arial", 9), relief=tk.FLAT)
        self.clear_btn.pack(side=tk.LEFT, padx=10)
        
        # Output Text Area with rich dark theme
        self.output_area = scrolledtext.ScrolledText(
            self,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#141517",
            fg="#cccccc",
            insertbackground="white",
            selectbackground="#1971c2",
            padx=12,
            pady=10,
        )
        self.output_area.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

    def setup_tags(self):
        """Configure syntax highlighting tags for rich drift report rendering."""
        self.output_area.tag_config("red", foreground="#ff6b6b", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("green", foreground="#51cf66", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("yellow", foreground="#ffd43b", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("gray", foreground="#adb5bd")
        self.output_area.tag_config("cyan", foreground="#38d9a9", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("blue", foreground="#74c0fc", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("header1", foreground="#4dabf7", font=("Consolas", 12, "bold"))
        self.output_area.tag_config("header2", foreground="#69db7c", font=("Consolas", 11, "bold"))
        self.output_area.tag_config("header3", foreground="#ffd43b", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("bold", foreground="#ffffff", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("code", foreground="#fcc419", font=("Consolas", 10))
        self.output_area.tag_config("bar_filled", foreground="#51cf66", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("bar_empty", foreground="#495057", font=("Consolas", 10))
        self.output_area.tag_config("alert_warn", foreground="#ffa94d", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("alert_info", foreground="#74c0fc", font=("Consolas", 10))
        self.output_area.tag_config("quote", foreground="#adb5bd", font=("Consolas", 10, "italic"))
        self.output_area.tag_config("table_border", foreground="#339af0", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("table_sep", foreground="#495057", font=("Consolas", 10))
        self.output_area.tag_config("table_header", foreground="#74c0fc", font=("Consolas", 10, "bold"))

    def browse_dir(self):
        folder = filedialog.askdirectory(title="Select Repository to Scan")
        if folder:
            self.target_dir.set(folder)

    def clear_output(self):
        self.output_area.delete(1.0, tk.END)

    def start_scan(self):
        repo = self.target_dir.get().strip()
        if not repo or not os.path.isdir(repo):
            messagebox.showerror("Error", "Please select a valid repository directory.")
            return

        # Disable run button while running
        self.run_btn.config(state=tk.DISABLED, text="Running...", bg="#495057")
        self.output_area.delete(1.0, tk.END)
        
        # Run in a background thread to keep GUI responsive
        threading.Thread(target=self.run_process, args=(repo,), daemon=True).start()

    def run_process(self, repo):
        cmd = [sys.executable, str(DRIFT_SCRIPT), "scan"]
        if self.no_llm.get():
            cmd.append("--no-llm")
        if self.no_images.get():
            cmd.append("--no-images")
        cmd.append(repo)

        self.log(f"Running command:\n{' '.join(cmd)}\n{'='*80}\n")
        
        # Force UTF-8 to prevent cp1252 crash on arrows/emojis
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=str(ROOT_DIR)
            )

            # Stream output in real-time
            for line in process.stdout:
                self.log(line)
            
            process.wait()
            self.log(f"\n{'='*80}\nScan complete. Exit code: {process.returncode}\n")
        except Exception as e:
            self.log(f"\nError running script: {e}\n")
        finally:
            # Re-enable button from main thread
            self.after(0, self.reset_ui)

    def reset_ui(self):
        self.run_btn.config(state=tk.NORMAL, text="▶ Run Scan", bg="#2b8a3e")

    def log(self, message):
        # Safely update GUI from background thread
        self.after(0, self._append_text, message)
        
    def _append_text(self, message):
        """Parse streaming text and apply syntax highlight tags dynamically."""
        lines = message.splitlines(keepends=True)
        
        token_pattern = re.compile(
            r'(🔴[^\s*`|]*|🟢[^\s*`|]*|🟡[^\s*`|]*|⚪[^\s*`|]*|'
            r'\bSTALE\b|\bOK\b|\bSUSPECT\b|\bBroken\b|\bVerified\b|\bCheck\b|'
            r'█+|░+|`[^`]+`|\*\*[^*]+\*\*)'
        )

        for line in lines:
            stripped = line.strip()

            # 1. Header 1: # ...
            if stripped.startswith("# ") and not stripped.startswith("## "):
                self.output_area.insert(tk.END, line, "header1")
                continue

            # 2. Header 2: ## ...
            if stripped.startswith("## ") and not stripped.startswith("### "):
                self.output_area.insert(tk.END, line, "header2")
                continue

            # 3. Header 3: ### ...
            if stripped.startswith("### "):
                self.output_area.insert(tk.END, line, "header3")
                continue

            # 4. Blockquote or alert: > ...
            if stripped.startswith("> "):
                if "⚠️" in stripped or "Heads-up" in stripped:
                    self.output_area.insert(tk.END, line, "alert_warn")
                elif "💡" in stripped or "🔎" in stripped:
                    self.output_area.insert(tk.END, line, "alert_info")
                else:
                    self.output_area.insert(tk.END, line, "quote")
                continue

            # 5. Table separator line: |:---|:---| or |---|---|
            if stripped.startswith("|") and re.match(r"^\|[\s:\-|]+\|$", stripped):
                self.output_area.insert(tk.END, line, "table_sep")
                continue

            # 6. Tokenized parsing for table pipes, badges, status, code, bold, bars
            token_pattern = re.compile(
                r'(\|)|(🔴[^\s*`|]*|🟢[^\s*`|]*|🟡[^\s*`|]*|⚪[^\s*`|]*|'
                r'\bSTALE\b|\bOK\b|\bSUSPECT\b|\bBroken\b|\bVerified\b|\bCheck\b|'
                r'█+|░+|`[^`]+`|\*\*[^*]+\*\*)'
            )

            pos = 0
            for m in token_pattern.finditer(line):
                start, end = m.span()
                if start > pos:
                    self.output_area.insert(tk.END, line[pos:start])
                
                if m.group(1):
                    # Table pipe divider
                    self.output_area.insert(tk.END, m.group(1), "table_border")
                else:
                    token = m.group(2)
                    tag = None
                    if any(x in token for x in ("🔴", "STALE", "Broken")):
                        tag = "red"
                    elif any(x in token for x in ("🟢", "OK", "Verified")):
                        tag = "green"
                    elif any(x in token for x in ("🟡", "SUSPECT", "Check")):
                        tag = "yellow"
                    elif any(x in token for x in ("⚪", "Skipped")):
                        tag = "gray"
                    elif token.startswith("█"):
                        tag = "bar_filled"
                    elif token.startswith("░"):
                        tag = "bar_empty"
                    elif token.startswith("`"):
                        tag = "code"
                    elif token.startswith("**"):
                        tag = "bold"

                    self.output_area.insert(tk.END, token, tag)
                pos = end

            if pos < len(line):
                self.output_area.insert(tk.END, line[pos:])

        self.output_area.see(tk.END)

if __name__ == "__main__":
    app = DriftGUI()
    app.mainloop()
