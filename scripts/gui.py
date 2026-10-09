#!/usr/bin/env python3
"""scripts/gui.py — codeCanon Docs Drift Detector & Gemma 4 Model Benchmark GUI.

Provides an interactive GUI for:
1. Scanning repositories and documentation for drift.
2. Selecting and comparing Gemma 4 models (31b-it, 26b-a4b-it, gemma4:e4b, and deterministic baseline).
3. Tracking and visualizing the exact number of tokens used (prompt, completion, total, cache).
4. Viewing side-by-side model comparison tables, Markdown reports, and unified patches.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

# Root directory of codeCanon
ROOT_DIR = Path(__file__).resolve().parent.parent
DRIFT_SCRIPT = ROOT_DIR / "scripts" / "drift.py"
FIXTURES_DIR = ROOT_DIR / "benchmark" / "fixtures"

GEMMA_MODELS = [
    {
        "id": "gemma-4-31b-it",
        "name": "Gemma 4 31B (API)",
        "mode": "api",
        "desc": "Frontier 31B dense instruction-tuned model via Gemini API",
    },
    {
        "id": "gemma-4-26b-a4b-it",
        "name": "Gemma 4 26B-A4B (API)",
        "mode": "api",
        "desc": "26B Mixture-of-Experts (4 active experts) via Gemini API",
    },
    {
        "id": "gemma4:e4b",
        "name": "Gemma 4 E4B (Local Ollama)",
        "mode": "local",
        "desc": "Quantized Edge 4B running locally on Ollama (localhost:11434)",
    },
    {
        "id": "gemma-4-custom",
        "name": "Custom Gemma 4 Tag...",
        "mode": "custom",
        "desc": "Specify custom model ID or tag",
    },
]


class CodeCanonGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("codeCanon — Gemma 4 Docs Drift Detector & Benchmark")
        self.geometry("1060x780")
        self.minsize(920, 640)

        # State Variables
        self.target_dir = tk.StringVar(value=str(FIXTURES_DIR / "next_app") if (FIXTURES_DIR / "next_app").exists() else str(ROOT_DIR))
        self.selected_model = tk.StringVar(value="gemma-4-31b-it")
        self.custom_model_id = tk.StringVar(value="gemma-4-31b-it")
        self.no_llm = tk.BooleanVar(value=False)
        self.no_images = tk.BooleanVar(value=False)
        self.simulate_mode = tk.BooleanVar(value=False)

        # Telemetry State
        self.total_tokens_var = tk.StringVar(value="0")
        self.prompt_tokens_var = tk.StringVar(value="0")
        self.completion_tokens_var = tk.StringVar(value="0")
        self.saved_tokens_var = tk.StringVar(value="0")
        self.runtime_var = tk.StringVar(value="0.00s")
        self.accuracy_var = tk.StringVar(value="--")

        # Process management
        self.current_process: subprocess.Popen | None = None
        self.is_running = False
        self.comparison_records: list[dict] = []

        self.apply_theme()
        self.create_widgets()
        self.check_initial_reports()

    def apply_theme(self):
        """Set dark aesthetic theme matching developer tool interfaces."""
        self.configure(bg="#181825")
        
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Configure dark ttk elements
        style.configure("TNotebook", background="#181825", borderwidth=0)
        style.configure("TNotebook.Tab", background="#313244", foreground="#cdd6f4", padding=[14, 6], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#45475a")], foreground=[("selected", "#ffffff")])

        style.configure("Treeview", background="#1e1e2e", foreground="#cdd6f4", fieldbackground="#1e1e2e", rowheight=28, font=("Consolas", 9))
        style.configure("Treeview.Heading", background="#313244", foreground="#ffffff", font=("Segoe UI", 9, "bold"), padding=[6, 4])
        style.map("Treeview", background=[("selected", "#585b70")], foreground=[("selected", "#ffffff")])

        style.configure("TCombobox", fieldbackground="#313244", background="#45475a", foreground="#ffffff")

    def create_widgets(self):
        # Top Container
        top_container = tk.Frame(self, bg="#181825", padx=14, pady=10)
        top_container.pack(fill=tk.X)

        # 1. Target Directory & Quick Pick
        target_frame = tk.Frame(top_container, bg="#181825")
        target_frame.pack(fill=tk.X, pady=(0, 8))

        lbl_target = tk.Label(target_frame, text="Target Repository / Fixture:", font=("Segoe UI", 10, "bold"), bg="#181825", fg="#cdd6f4")
        lbl_target.pack(side=tk.LEFT)

        ent_target = tk.Entry(target_frame, textvariable=self.target_dir, font=("Consolas", 10), bg="#313244", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT)
        ent_target.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, ipady=4)

        btn_browse = tk.Button(target_frame, text="📁 Browse...", command=self.browse_dir, bg="#45475a", fg="#ffffff", relief=tk.FLAT, font=("Segoe UI", 9), padx=10)
        btn_browse.pack(side=tk.LEFT, padx=(0, 6))

        # Quick Pick Fixture Menu
        btn_fixtures = tk.Menubutton(target_frame, text="⚡ Quick Picks ▾", bg="#585b70", fg="#ffffff", relief=tk.FLAT, font=("Segoe UI", 9, "bold"), padx=8)
        fix_menu = tk.Menu(btn_fixtures, tearoff=0, bg="#313244", fg="#ffffff", activebackground="#89b4fa")
        
        # Populate fixture items
        if FIXTURES_DIR.exists():
            for fix_dir in sorted(FIXTURES_DIR.iterdir()):
                if fix_dir.is_dir() and (fix_dir / "package.json").exists():
                    fix_menu.add_command(label=f"Fixture: {fix_dir.name}", command=lambda p=str(fix_dir): self.target_dir.set(p))
            fix_menu.add_separator()
        fix_menu.add_command(label="codeCanon Root Workspace", command=lambda: self.target_dir.set(str(ROOT_DIR)))
        btn_fixtures["menu"] = fix_menu
        btn_fixtures.pack(side=tk.LEFT)

        # 2. Controls & Gemma Model Selection
        controls_frame = tk.Frame(top_container, bg="#252538", padx=12, pady=10, relief=tk.FLAT, highlightbackground="#313244", highlightthickness=1)
        controls_frame.pack(fill=tk.X, pady=4)

        # Gemma 4 Model Selector
        model_sec = tk.Frame(controls_frame, bg="#252538")
        model_sec.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(model_sec, text="Gemma 4 Model:", font=("Segoe UI", 10, "bold"), bg="#252538", fg="#89b4fa").grid(row=0, column=0, sticky="w", padx=(0, 6))

        model_values = [f"{m['name']}  ({m['id']})" for m in GEMMA_MODELS]
        self.model_combo = ttk.Combobox(model_sec, values=model_values, state="readonly", width=36)
        self.model_combo.current(0)
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_selected)
        self.model_combo.grid(row=0, column=1, sticky="w", padx=4)

        # Options checkbuttons
        opts_sec = tk.Frame(model_sec, bg="#252538")
        opts_sec.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        tk.Checkbutton(opts_sec, text="--no-llm (Deterministic Baseline)", variable=self.no_llm, bg="#252538", fg="#cdd6f4", selectcolor="#1e1e2e", activebackground="#252538", activeforeground="#ffffff", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 10))
        tk.Checkbutton(opts_sec, text="--no-images (Skip Screenshots)", variable=self.no_images, bg="#252538", fg="#cdd6f4", selectcolor="#1e1e2e", activebackground="#252538", activeforeground="#ffffff", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(opts_sec, text="🧪 Benchmark Simulation Mode", variable=self.simulate_mode, bg="#252538", fg="#a6e3a1", selectcolor="#1e1e2e", activebackground="#252538", activeforeground="#ffffff", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=10)

        # Action Buttons Section
        btn_sec = tk.Frame(controls_frame, bg="#252538")
        btn_sec.pack(side=tk.RIGHT, fill=tk.Y)

        self.btn_run = tk.Button(btn_sec, text="▶ Run Scan", command=self.start_single_scan, bg="#2ea043", fg="#ffffff", activebackground="#2c974b", activeforeground="#ffffff", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=16, pady=4)
        self.btn_run.pack(side=tk.LEFT, padx=4)

        self.btn_compare = tk.Button(btn_sec, text="⚡ Compare Gemma 4 Models", command=self.start_model_comparison, bg="#1f6feb", fg="#ffffff", activebackground="#388bfd", activeforeground="#ffffff", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=14, pady=4)
        self.btn_compare.pack(side=tk.LEFT, padx=4)

        self.btn_stop = tk.Button(btn_sec, text="⏹ Stop", command=self.stop_execution, bg="#da3633", fg="#ffffff", state=tk.DISABLED, relief=tk.FLAT, font=("Segoe UI", 9), padx=10, pady=4)
        self.btn_stop.pack(side=tk.LEFT, padx=4)

        # 3. Live Token & Metric KPI Cards Bar
        self.create_kpi_bar(top_container)

        # 4. Notebook Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        # Tab 1: Terminal Log
        self.tab_log = tk.Frame(self.notebook, bg="#181825")
        self.notebook.add(self.tab_log, text="🖥️ Live Terminal Log")
        self.create_log_tab()

        # Tab 2: Gemma 4 Model Comparison
        self.tab_compare = tk.Frame(self.notebook, bg="#181825")
        self.notebook.add(self.tab_compare, text="⚖️ Gemma 4 Model Comparison")
        self.create_comparison_tab()

        # Tab 3: Reports & Patches Viewer
        self.tab_report = tk.Frame(self.notebook, bg="#181825")
        self.notebook.add(self.tab_report, text="📄 Drift Report & Patches")
        self.create_report_tab()

        # Bottom Status Bar
        self.status_bar = tk.Label(self, text="Ready. Choose a repository and run a scan or comparison.", bd=1, relief=tk.FLAT, anchor=tk.W, bg="#11111b", fg="#a6adc8", font=("Segoe UI", 9), padx=10, pady=3)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_kpi_bar(self, parent):
        """Build KPI metric cards showing tokens and drift statistics."""
        kpi_frame = tk.Frame(parent, bg="#181825", pady=6)
        kpi_frame.pack(fill=tk.X)

        cards = [
            ("🔢 Total Tokens Used", self.total_tokens_var, "#cba6f7", "tokens across all calls"),
            ("📥 Prompt Tokens", self.prompt_tokens_var, "#89b4fa", "input prompt context"),
            ("📤 Output Tokens", self.completion_tokens_var, "#f38ba8", "generated completions"),
            ("💾 Tokens Saved (Cache)", self.saved_tokens_var, "#a6e3a1", "saved via cache hits"),
            ("⏱️ Scan Runtime", self.runtime_var, "#fab387", "elapsed scan duration"),
            ("🎯 Accuracy", self.accuracy_var, "#94e2d5", "verified claims / total"),
        ]

        for idx, (title, var, color, subtitle) in enumerate(cards):
            card = tk.Frame(kpi_frame, bg="#252538", padx=10, pady=6, relief=tk.FLAT, highlightbackground="#313244", highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)

            lbl_t = tk.Label(card, text=title, font=("Segoe UI", 8, "bold"), bg="#252538", fg=color)
            lbl_t.pack(anchor="w")

            lbl_v = tk.Label(card, textvariable=var, font=("Consolas", 14, "bold"), bg="#252538", fg="#ffffff")
            lbl_v.pack(anchor="w", pady=(1, 0))

            lbl_sub = tk.Label(card, text=subtitle, font=("Segoe UI", 7), bg="#252538", fg="#6c7086")
            lbl_sub.pack(anchor="w")

    def create_log_tab(self):
        # Toolbar above console
        tb = tk.Frame(self.tab_log, bg="#181825", pady=4)
        tb.pack(fill=tk.X)

        btn_clear = tk.Button(tb, text="Clear Console", command=self.clear_log, bg="#313244", fg="#cdd6f4", relief=tk.FLAT, font=("Segoe UI", 8), padx=8)
        btn_clear.pack(side=tk.RIGHT, padx=4)

        # Scrolled terminal
        self.output_area = scrolledtext.ScrolledText(self.tab_log, wrap=tk.WORD, font=("Consolas", 10), bg="#1e1e2e", fg="#cdd6f4", insertbackground="#ffffff", relief=tk.FLAT)
        self.output_area.pack(fill=tk.BOTH, expand=True)

        # Tag configurations for syntax highlighting
        self.output_area.tag_config("green", foreground="#a6e3a1", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("yellow", foreground="#f9e2af", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("red", foreground="#f38ba8", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("cyan", foreground="#89dceb", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("blue", foreground="#89b4fa", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("purple", foreground="#cba6f7", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("gray", foreground="#6c7086")
        self.output_area.tag_config("bold", foreground="#ffffff", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("header1", foreground="#89b4fa", font=("Consolas", 12, "bold"))
        self.output_area.tag_config("header2", foreground="#a6e3a1", font=("Consolas", 11, "bold"))
        self.output_area.tag_config("header3", foreground="#f9e2af", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("code", foreground="#fab387", font=("Consolas", 10))
        self.output_area.tag_config("bar_filled", foreground="#a6e3a1", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("bar_empty", foreground="#585b70", font=("Consolas", 10))
        self.output_area.tag_config("alert_warn", foreground="#fab387", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("alert_info", foreground="#89b4fa", font=("Consolas", 10))
        self.output_area.tag_config("quote", foreground="#a6adc8", font=("Consolas", 10, "italic"))
        self.output_area.tag_config("table_border", foreground="#89b4fa", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("table_sep", foreground="#585b70", font=("Consolas", 10))
        self.output_area.tag_config("table_header", foreground="#89dceb", font=("Consolas", 10, "bold"))

    def create_comparison_tab(self):
        # Top toolbar
        toolbar = tk.Frame(self.tab_compare, bg="#181825", pady=6)
        toolbar.pack(fill=tk.X)

        btn_run_comp = tk.Button(toolbar, text="⚡ Run Full Gemma 4 Comparison", command=self.start_model_comparison, bg="#89b4fa", fg="#11111b", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12, pady=3)
        btn_run_comp.pack(side=tk.LEFT, padx=4)

        btn_copy_md = tk.Button(toolbar, text="📋 Copy Table as Markdown", command=self.copy_comparison_markdown, bg="#45475a", fg="#ffffff", font=("Segoe UI", 9), relief=tk.FLAT, padx=10, pady=3)
        btn_copy_md.pack(side=tk.LEFT, padx=4)

        btn_export_json = tk.Button(toolbar, text="💾 Export JSON", command=self.export_comparison_json, bg="#45475a", fg="#ffffff", font=("Segoe UI", 9), relief=tk.FLAT, padx=10, pady=3)
        btn_export_json.pack(side=tk.LEFT, padx=4)

        btn_clear = tk.Button(toolbar, text="🗑️ Clear", command=self.clear_comparison, bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9), relief=tk.FLAT, padx=8, pady=3)
        btn_clear.pack(side=tk.RIGHT, padx=4)

        # Treeview Comparison Table
        columns = ("model", "mode", "total_tokens", "prompt_tokens", "completion_tokens", "runtime", "stale", "suspect", "ok", "accuracy", "calls", "verdict")
        self.tree = ttk.Treeview(self.tab_compare, columns=columns, show="headings", selectmode="browse")

        headers = [
            ("model", "Model Name", 170),
            ("mode", "Mode", 70),
            ("total_tokens", "Total Tokens", 100),
            ("prompt_tokens", "Prompt Tok", 90),
            ("completion_tokens", "Output Tok", 90),
            ("runtime", "Time (s)", 75),
            ("stale", "Broken 🔴", 70),
            ("suspect", "Check 🟡", 70),
            ("ok", "OK 🟢", 70),
            ("accuracy", "Accuracy", 80),
            ("calls", "Calls/Hits", 80),
            ("verdict", "Verdict", 120),
        ]

        for col_id, heading_text, width in headers:
            self.tree.heading(col_id, text=heading_text, command=lambda c=col_id: self.sort_tree(c, False))
            self.tree.column(col_id, width=width, anchor=tk.CENTER if col_id not in ("model", "verdict") else tk.W)

        tree_scroll = ttk.Scrollbar(self.tab_compare, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def create_report_tab(self):
        # Toolbar
        rep_bar = tk.Frame(self.tab_report, bg="#181825", pady=4)
        rep_bar.pack(fill=tk.X)

        tk.Button(rep_bar, text="🔄 Refresh from disk", command=self.reload_reports, bg="#45475a", fg="#ffffff", font=("Segoe UI", 8), relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(rep_bar, text="Open Report File", command=self.open_report_file, bg="#313244", fg="#cdd6f4", font=("Segoe UI", 8), relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=4)

        # Scrolled Text for Markdown and Patches
        self.report_area = scrolledtext.ScrolledText(self.tab_report, wrap=tk.WORD, font=("Consolas", 10), bg="#1e1e2e", fg="#cdd6f4", insertbackground="#ffffff", relief=tk.FLAT)
        self.report_area.pack(fill=tk.BOTH, expand=True)

    def on_model_selected(self, event=None):
        idx = self.model_combo.current()
        if 0 <= idx < len(GEMMA_MODELS):
            m = GEMMA_MODELS[idx]
            if m["id"] == "gemma-4-custom":
                custom = filedialog.askstring if hasattr(filedialog, "askstring") else None
                # Use simple prompt
                new_id = self.prompt_custom_model()
                if new_id:
                    self.selected_model.set(new_id)
            else:
                self.selected_model.set(m["id"])

    def prompt_custom_model(self) -> str:
        win = tk.Toplevel(self)
        win.title("Custom Model ID")
        win.geometry("380x130")
        win.configure(bg="#1e1e2e")
        win.transient(self)
        win.grab_set()

        tk.Label(win, text="Enter Gemma Model ID or Tag:", font=("Segoe UI", 10, "bold"), bg="#1e1e2e", fg="#ffffff").pack(pady=10)
        entry = tk.Entry(win, textvariable=self.custom_model_id, font=("Consolas", 10), width=30)
        entry.pack(pady=4)

        result = [""]
        def on_ok():
            result[0] = entry.get().strip()
            win.destroy()

        tk.Button(win, text="OK", command=on_ok, bg="#2ea043", fg="#ffffff", font=("Segoe UI", 9, "bold"), padx=12).pack(pady=8)
        self.wait_window(win)
        return result[0]

    def browse_dir(self):
        folder = filedialog.askdirectory(title="Select Repository to Scan", initialdir=str(ROOT_DIR))
        if folder:
            self.target_dir.set(folder)

    def clear_log(self):
        self.output_area.delete(1.0, tk.END)

    def append_log(self, text: str, tag: str | None = None):
        if tag is not None:
            self.output_area.insert(tk.END, text, tag)
            self.output_area.see(tk.END)
            return

        lines = text.splitlines(keepends=True)
        for line in lines:
            stripped = line.strip()

            if stripped.startswith("# ") and not stripped.startswith("## "):
                self.output_area.insert(tk.END, line, "header1")
                continue
            if stripped.startswith("## ") and not stripped.startswith("### "):
                self.output_area.insert(tk.END, line, "header2")
                continue
            if stripped.startswith("### "):
                self.output_area.insert(tk.END, line, "header3")
                continue
            if stripped.startswith("> "):
                if "⚠️" in stripped or "Heads-up" in stripped:
                    self.output_area.insert(tk.END, line, "alert_warn")
                elif "💡" in stripped or "🔎" in stripped:
                    self.output_area.insert(tk.END, line, "alert_info")
                else:
                    self.output_area.insert(tk.END, line, "quote")
                continue
            if stripped.startswith("|") and re.match(r"^\|[\s:\-|]+\|$", stripped):
                self.output_area.insert(tk.END, line, "table_sep")
                continue

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
                    self.output_area.insert(tk.END, m.group(1), "table_border")
                else:
                    tok = m.group(2)
                    t = None
                    if any(x in tok for x in ("🔴", "STALE", "Broken")):
                        t = "red"
                    elif any(x in tok for x in ("🟢", "OK", "Verified")):
                        t = "green"
                    elif any(x in tok for x in ("🟡", "SUSPECT", "Check")):
                        t = "yellow"
                    elif any(x in tok for x in ("⚪", "Skipped")):
                        t = "gray"
                    elif tok.startswith("█"):
                        t = "bar_filled"
                    elif tok.startswith("░"):
                        t = "bar_empty"
                    elif tok.startswith("`"):
                        t = "code"
                    elif tok.startswith("**"):
                        t = "bold"

                    self.output_area.insert(tk.END, tok, t)
                pos = end

            if pos < len(line):
                self.output_area.insert(tk.END, line[pos:])

        self.output_area.see(tk.END)

    def set_running_state(self, running: bool):
        self.is_running = running
        if running:
            self.btn_run.config(state=tk.DISABLED)
            self.btn_compare.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.status_bar.config(text="Running scan... please wait.")
        else:
            self.btn_run.config(state=tk.NORMAL)
            self.btn_compare.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.status_bar.config(text="Ready.")

    def stop_execution(self):
        if self.current_process and self.current_process.poll() is None:
            self.append_log("\n[STOPPING PROCESS...]\n", "red")
            try:
                self.current_process.terminate()
            except Exception:
                pass
        self.is_running = False
        self.set_running_state(False)

    def start_single_scan(self):
        repo = self.target_dir.get().strip()
        if not repo or not os.path.isdir(repo):
            messagebox.showerror("Error", "Please select a valid repository directory.")
            return

        self.set_running_state(True)
        self.clear_log()
        self.notebook.select(self.tab_log)

        model_id = self.selected_model.get()
        no_llm = self.no_llm.get()
        no_images = self.no_images.get()
        sim_mode = self.simulate_mode.get()

        threading.Thread(
            target=self._run_scan_thread,
            args=(repo, model_id, no_llm, no_images, sim_mode, True),
            daemon=True
        ).start()

    def start_model_comparison(self):
        repo = self.target_dir.get().strip()
        if not repo:
            messagebox.showerror("Error", "Please select a target repository.")
            return

        self.set_running_state(True)
        self.clear_log()
        self.notebook.select(self.tab_compare)

        sim_mode = self.simulate_mode.get()
        no_images = self.no_images.get()

        threading.Thread(
            target=self._run_comparison_thread,
            args=(repo, no_images, sim_mode),
            daemon=True
        ).start()

    def _run_scan_thread(self, repo: str, model_id: str, no_llm: bool, no_images: bool, sim_mode: bool, update_kpis: bool) -> dict:
        cmd = [sys.executable, str(DRIFT_SCRIPT), "scan", repo]
        if no_llm:
            cmd.append("--no-llm")
        else:
            cmd.extend(["--model", model_id])
        if no_images:
            cmd.append("--no-images")
        self.append_log(f"================================================================================\n", "blue")
        self.append_log(f"Starting Scan: {repo}\n", "bold")
        self.append_log(f"Model: {model_id} | No-LLM: {no_llm} | Sim-Mode: {sim_mode}\n", "purple")
        self.append_log(f"Command: {' '.join(cmd)}\n", "cyan")
        self.append_log(f"================================================================================\n\n", "blue")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if sim_mode:
            env["DRIFT_SIMULATE"] = "1"

        start_time = time.perf_counter()
        token_stats = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "saved_tokens": 0}
        report_data = None

        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=str(ROOT_DIR)
            )

            # Stream output
            for line in self.current_process.stdout:
                self.append_log(line)

            self.current_process.wait()
            elapsed = time.perf_counter() - start_time

            # Load report JSON
            report_file = ROOT_DIR / "drift-report.json"
            if report_file.exists():
                try:
                    report_data = json.loads(report_file.read_text(encoding="utf-8"))
                    stats = report_data.get("metadata", {}).get("stats", {})
                    token_stats = stats.get("tokens", token_stats)
                except Exception as e:
                    self.append_log(f"[Warning loading JSON: {e}]\n", "yellow")

            if update_kpis:
                self.after(0, self._update_kpi_widgets, token_stats, elapsed, report_data)
                self.after(0, self.reload_reports)

            return {
                "model": model_id if not no_llm else "None (--no-llm)",
                "mode": "api" if "api" in model_id or "31b" in model_id or "26b" in model_id else "local" if "e4b" in model_id else "deterministic",
                "tokens": token_stats,
                "runtime": elapsed,
                "report": report_data
            }

        except Exception as exc:
            self.append_log(f"\n[Execution Error]: {exc}\n", "red")
            return {
                "model": model_id,
                "mode": "error",
                "tokens": token_stats,
                "runtime": 0.0,
                "report": None
            }
        finally:
            if update_kpis:
                self.after(0, self.set_running_state, False)

    def _update_kpi_widgets(self, token_stats: dict, elapsed: float, report_data: dict | None):
        total = token_stats.get("total_tokens", 0)
        prompt = token_stats.get("prompt_tokens", 0)
        compl = token_stats.get("completion_tokens", 0)
        saved = token_stats.get("saved_tokens", 0)

        self.total_tokens_var.set(f"{total:,}")
        self.prompt_tokens_var.set(f"{prompt:,}")
        self.completion_tokens_var.set(f"{compl:,}")
        self.saved_tokens_var.set(f"{saved:,}")
        self.runtime_var.set(f"{elapsed:.2f}s")

        if report_data:
            stats = report_data.get("metadata", {}).get("stats", {})
            acc = stats.get("accuracy_pct", "--")
            self.accuracy_var.set(f"{acc}%")
        else:
            self.accuracy_var.set("--")

    def _run_comparison_thread(self, repo: str, no_images: bool, sim_mode: bool):
        """Execute benchmark comparison across all Gemma 4 models + baseline."""
        models_to_test = [
            ("gemma-4-31b-it", False, "Gemma 4 31B (API)"),
            ("gemma-4-26b-a4b-it", False, "Gemma 4 26B-A4B (API)"),
            ("gemma4:e4b", False, "Gemma 4 E4B (Local)"),
            ("baseline", True, "Deterministic (--no-llm)"),
        ]

        self.append_log("\n🚀 STARTING GEMMA 4 MODEL COMPARISON BENCHMARK SUITE\n", "bold")
        self.append_log(f"Evaluating {len(models_to_test)} model configurations against {repo}...\n\n", "purple")

        for model_id, no_llm, label in models_to_test:
            if not self.is_running:
                break

            self.append_log(f"--- Running {label} ---\n", "blue")
            res = self._run_scan_thread(repo, model_id, no_llm, no_images, sim_mode, False)
            self.after(0, self._add_comparison_row, res, label)
            time.sleep(0.5)

        self.append_log("\n✅ GEMMA 4 COMPARISON COMPLETE. See comparison table for metrics.\n", "green")
        self.after(0, self.set_running_state, False)
        self.after(0, self.reload_reports)

    def _add_comparison_row(self, res: dict, display_label: str):
        tokens = res.get("tokens", {})
        total_tok = tokens.get("total_tokens", 0)
        prompt_tok = tokens.get("prompt_tokens", 0)
        compl_tok = tokens.get("completion_tokens", 0)
        calls = tokens.get("calls", 0)
        hits = tokens.get("cache_hits", 0)
        runtime = res.get("runtime", 0.0)

        report = res.get("report") or {}
        stats = report.get("metadata", {}).get("stats", {})
        broken = stats.get("broken", "--")
        check = stats.get("check", "--")
        verified = stats.get("verified", "--")
        acc = f"{stats.get('accuracy_pct', 0)}%" if stats else "--"
        verdict = report.get("summary", {}).get("verdict", "Complete")

        mode = "Local" if "e4b" in display_label.lower() else "API" if "api" in display_label.lower() else "Deterministic"

        row = (
            display_label,
            mode,
            f"{total_tok:,}",
            f"{prompt_tok:,}",
            f"{compl_tok:,}",
            f"{runtime:.2f}",
            str(broken),
            str(check),
            str(verified),
            acc,
            f"{calls}/{hits}",
            verdict
        )

        self.tree.insert("", tk.END, values=row)
        self.comparison_records.append({
            "model": display_label,
            "mode": mode,
            "total_tokens": total_tok,
            "prompt_tokens": prompt_tok,
            "completion_tokens": compl_tok,
            "runtime_s": round(runtime, 3),
            "broken": broken,
            "check": check,
            "verified": verified,
            "accuracy": acc,
            "calls": calls,
            "cache_hits": hits,
            "verdict": verdict,
        })

    def clear_comparison(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.comparison_records.clear()

    def copy_comparison_markdown(self):
        if not self.comparison_records:
            messagebox.showinfo("Empty", "No comparison results yet. Run a comparison first.")
            return

        lines = [
            "### Gemma 4 Model Benchmark & Token Comparison",
            "",
            "| Model | Mode | Total Tokens | Prompt Tok | Output Tok | Time (s) | Broken 🔴 | Check 🟡 | Verified 🟢 | Accuracy | Calls/Hits | Verdict |",
            "|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|",
        ]

        for r in self.comparison_records:
            lines.append(
                f"| **{r['model']}** | {r['mode']} | {r['total_tokens']:,} | {r['prompt_tokens']:,} | {r['completion_tokens']:,} | {r['runtime_s']}s | {r['broken']} | {r['check']} | {r['verified']} | {r['accuracy']} | {r['calls']}/{r['cache_hits']} | {r['verdict']} |"
            )

        md = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(md)
        messagebox.showinfo("Copied", "Comparison markdown table copied to clipboard! Ready to paste into progress.md or README.")

    def export_comparison_json(self):
        if not self.comparison_records:
            messagebox.showinfo("Empty", "No comparison results yet.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"gemma4-comparison-{int(time.time())}.json"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "target_repo": self.target_dir.get(),
                    "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "benchmarks": self.comparison_records
                }, f, indent=2)
            messagebox.showinfo("Saved", f"Comparison exported to {file_path}")

    def sort_tree(self, col: str, reverse: bool):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            items.sort(key=lambda t: float(t[0].replace(",", "").replace("%", "").replace("s", "")), reverse=reverse)
        except ValueError:
            items.sort(reverse=reverse)

        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

        self.tree.heading(col, command=lambda: self.sort_tree(col, not reverse))

    def reload_reports(self):
        md_file = ROOT_DIR / "drift-report.md"
        patch_file = ROOT_DIR / "drift-report.patch"
        
        self.report_area.delete(1.0, tk.END)

        if md_file.exists():
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                self.report_area.insert(tk.END, content)
            except Exception as e:
                self.report_area.insert(tk.END, f"Error reading drift-report.md: {e}")
        else:
            self.report_area.insert(tk.END, "# No drift-report.md generated yet.\nRun a scan to generate the report.")

        if patch_file.exists():
            try:
                patch_content = patch_file.read_text(encoding="utf-8", errors="replace")
                self.report_area.insert(tk.END, "\n\n" + "="*80 + "\nUNIFIED PATCH (drift-report.patch):\n" + "="*80 + "\n\n")
                self.report_area.insert(tk.END, patch_content)
            except Exception:
                pass

    def check_initial_reports(self):
        self.reload_reports()

    def open_report_file(self):
        md_file = ROOT_DIR / "drift-report.md"
        if md_file.exists():
            try:
                if sys.platform.startswith("win"):
                    os.startfile(str(md_file))
                else:
                    subprocess.run(["xdg-open", str(md_file)])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
        else:
            messagebox.showinfo("Not Found", "drift-report.md does not exist yet. Run a scan first.")

if __name__ == "__main__":
    app = CodeCanonGUI()
    app.mainloop()
