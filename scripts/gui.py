import os
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
        self.geometry("850x650")
        
        # Variables
        self.target_dir = tk.StringVar()
        self.no_llm = tk.BooleanVar(value=False)
        self.no_images = tk.BooleanVar(value=False)
        
        self.create_widgets()

    def create_widgets(self):
        # Top Frame for controls
        control_frame = tk.Frame(self, padx=10, pady=10)
        control_frame.pack(fill=tk.X)
        
        # Directory Selection
        tk.Label(control_frame, text="Target Repository:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(control_frame, textvariable=self.target_dir, width=60, font=("Arial", 10)).grid(row=0, column=1, padx=10)
        tk.Button(control_frame, text="Browse...", command=self.browse_dir).grid(row=0, column=2)
        
        # Flags
        options_frame = tk.Frame(control_frame)
        options_frame.grid(row=1, column=1, sticky="w", pady=5)
        tk.Checkbutton(options_frame, text="--no-llm (Fast deterministic mode)", variable=self.no_llm).pack(side=tk.LEFT)
        tk.Checkbutton(options_frame, text="--no-images (Skip screenshots)", variable=self.no_images).pack(side=tk.LEFT, padx=10)
        
        # Run Button
        self.run_btn = tk.Button(control_frame, text="▶ Run Scan", command=self.start_scan, bg="#2ea043", fg="white", font=("Arial", 10, "bold"), width=15)
        self.run_btn.grid(row=2, column=1, pady=10, sticky="w")
        
        # Output Text Area
        self.output_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Consolas", 10), bg="#1e1e1e", fg="#cccccc")
        self.output_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def browse_dir(self):
        folder = filedialog.askdirectory(title="Select Repository to Scan")
        if folder:
            self.target_dir.set(folder)

    def start_scan(self):
        repo = self.target_dir.get()
        if not repo or not os.path.isdir(repo):
            messagebox.showerror("Error", "Please select a valid repository directory.")
            return

        # Disable run button while running
        self.run_btn.config(state=tk.DISABLED, text="Running...")
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
        
        # Force UTF-8 to prevent cp1252 crash on arrows
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
            self.log(f"\n{'='*80}\nScan complete. Exit code: {process.returncode}")
        except Exception as e:
            self.log(f"\nError running script: {e}")
        finally:
            # Re-enable button from main thread
            self.after(0, self.reset_ui)

    def reset_ui(self):
        self.run_btn.config(state=tk.NORMAL, text="▶ Run Scan")

    def log(self, message):
        # Safely update GUI from background thread
        self.after(0, self._append_text, message)
        
    def _append_text(self, message):
        self.output_area.insert(tk.END, message)
        self.output_area.see(tk.END)

if __name__ == "__main__":
    app = DriftGUI()
    app.mainloop()

