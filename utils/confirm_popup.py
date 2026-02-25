"""
Tkinter confirmation popup for chatbot auto-fill.
Shows question + auto-filled answer for user verification before saving.
Uses a persistent hidden root window for faster popup creation.
Supports text input, radio buttons (single-select), and checkboxes (multi-select).
"""

import tkinter as tk
from tkinter import ttk


class ConfirmPopup:
    """Popup dialog to confirm auto-filled chatbot answers."""

    def __init__(self):
        self.disabled = False  # If True, auto-submit all future answers
        # Create a persistent hidden root window (avoids re-init overhead)
        self._root = tk.Tk()
        self._root.withdraw()  # Hide it
        self._setup_styles()

    def _setup_styles(self):
        """Configure ttk styles once."""
        style = ttk.Style(self._root)
        style.theme_use("clam")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 11))
        style.configure("Title.TLabel", background="#1e1e2e", foreground="#89b4fa", font=("Segoe UI", 13, "bold"))
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("TRadiobutton", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        style.configure("TCheckbutton", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        # Confidence styles
        style.configure("Auto.TLabel", background="#1e1e2e", foreground="#a6e3a1", font=("Segoe UI", 9, "italic"))
        style.configure("Learned.TLabel", background="#1e1e2e", foreground="#f9e2af", font=("Segoe UI", 9, "italic"))
        style.configure("Unknown.TLabel", background="#1e1e2e", foreground="#f38ba8", font=("Segoe UI", 9, "italic"))

    def show(self, question, answer, options=None, confidence="auto", multi_select=False, can_skip=False):
        """
        Show a confirmation popup.

        Args:
            question: The chatbot question text
            answer: The auto-filled answer (may be empty for unknown questions).
                    For multi_select, this should be a list of selected values.
            options: Optional list of options (for radio or checkbox questions)
            confidence: "auto", "learned", or "unknown"
            multi_select: If True, show checkboxes instead of radio buttons
            can_skip: If True, show a "Skip Question" button

        Returns:
            (action, answer) where action is "submit", "cancel", "disable", or "skip"
            For multi_select, answer is a list of selected values.
        """
        # If disabled, auto-submit
        if self.disabled:
            return "submit", answer

        result = {"action": "cancel", "answer": answer}

        # Use Toplevel (much faster than creating new Tk root each time)
        win = tk.Toplevel(self._root)
        win.title("Naukri Auto-Apply — Confirm Answer")
        win.attributes("-topmost", True)
        win.resizable(True, True)

        # Fixed window size — options scroll inside, buttons always visible
        window_width = 550
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        window_height = min(520, screen_height - 80)

        x = max((screen_width - window_width) // 2, 0)
        y = max((screen_height - window_height) // 2, 0)
        win.geometry(f"{window_width}x{window_height}+{x}+{y}")
        win.configure(bg="#1e1e2e")

        # --- Confidence badge ---
        conf_labels = {
            "auto": "✅ Auto-filled from config",
            "learned": "📚 Learned from history",
            "unknown": "❓ Unknown — please fill",
        }
        conf_styles = {"auto": "Auto.TLabel", "learned": "Learned.TLabel", "unknown": "Unknown.TLabel"}

        conf_label = ttk.Label(win, text=conf_labels.get(confidence, ""), style=conf_styles.get(confidence, "Auto.TLabel"))
        conf_label.pack(pady=(10, 2))

        # --- Question ---
        q_frame = ttk.Frame(win)
        q_frame.pack(fill="x", padx=20, pady=(5, 10))

        ttk.Label(q_frame, text="Question:", style="Title.TLabel").pack(anchor="w")
        q_text = tk.Text(q_frame, height=3, wrap="word", font=("Segoe UI", 10),
                         bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                         relief="flat", padx=8, pady=6)
        q_text.insert("1.0", question)
        q_text.configure(state="disabled")
        q_text.pack(fill="x", pady=(4, 0))

        # --- Answer ---
        a_frame = ttk.Frame(win)
        a_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        ttk.Label(a_frame, text="Answer:", style="Title.TLabel").pack(anchor="w")

        if options and multi_select:
            # Multi-select checkboxes
            pre_selected = answer if isinstance(answer, list) else []

            options_canvas = tk.Canvas(a_frame, bg="#1e1e2e", highlightthickness=0)
            scrollbar = ttk.Scrollbar(a_frame, orient="vertical", command=options_canvas.yview)
            options_inner = ttk.Frame(options_canvas)

            options_inner.bind("<Configure>", lambda e: options_canvas.configure(scrollregion=options_canvas.bbox("all")))
            options_canvas.create_window((0, 0), window=options_inner, anchor="nw")
            options_canvas.configure(yscrollcommand=scrollbar.set)

            check_vars = {}
            for opt in options:
                var = tk.BooleanVar(value=(opt in pre_selected))
                check_vars[opt] = var
                cb = ttk.Checkbutton(options_inner, text=opt, variable=var, style="TCheckbutton")
                cb.pack(anchor="w", pady=2, padx=10)

            options_canvas.pack(side="left", fill="both", expand=True, pady=(4, 0))
            if len(options) > 8:
                scrollbar.pack(side="right", fill="y", pady=(4, 0))

            def get_answer():
                return [opt for opt, var in check_vars.items() if var.get()]

        elif options:
            # Radio button options (single-select)
            selected_var = tk.StringVar(value=answer if answer else "")

            options_canvas = tk.Canvas(a_frame, bg="#1e1e2e", highlightthickness=0)
            scrollbar = ttk.Scrollbar(a_frame, orient="vertical", command=options_canvas.yview)
            options_inner = ttk.Frame(options_canvas)

            options_inner.bind("<Configure>", lambda e: options_canvas.configure(scrollregion=options_canvas.bbox("all")))
            options_canvas.create_window((0, 0), window=options_inner, anchor="nw")
            options_canvas.configure(yscrollcommand=scrollbar.set)

            for opt in options:
                rb = ttk.Radiobutton(options_inner, text=opt, value=opt,
                                     variable=selected_var, style="TRadiobutton")
                rb.pack(anchor="w", pady=2, padx=10)

            options_canvas.pack(side="left", fill="both", expand=True, pady=(4, 0))
            if len(options) > 8:
                scrollbar.pack(side="right", fill="y", pady=(4, 0))

            def get_answer():
                return selected_var.get()
        else:
            # Text input
            a_text = tk.Text(a_frame, height=4, wrap="word", font=("Segoe UI", 10),
                             bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                             relief="flat", padx=8, pady=6)
            a_text.insert("1.0", answer if answer else "")
            a_text.pack(fill="both", expand=True, pady=(4, 0))

            def get_answer():
                return a_text.get("1.0", "end-1c").strip()

        # --- Buttons ---
        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))

        def on_submit():
            result["action"] = "submit"
            result["answer"] = get_answer()
            win.destroy()

        def on_cancel():
            result["action"] = "cancel"
            win.destroy()

        def on_disable():
            result["action"] = "disable"
            result["answer"] = get_answer()
            self.disabled = True
            win.destroy()

        # Submit button (green)
        tk.Button(btn_frame, text="✅ Submit", command=on_submit,
                  bg="#a6e3a1", fg="#1e1e2e", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=16, pady=6, cursor="hand2").pack(side="left", padx=(0, 8))

        # Cancel button (red)
        tk.Button(btn_frame, text="❌ Cancel (Skip Job)", command=on_cancel,
                  bg="#f38ba8", fg="#1e1e2e", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=16, pady=6, cursor="hand2").pack(side="left", padx=(0, 8))

        # Disable button (yellow)
        tk.Button(btn_frame, text="⚡ Disable Popups", command=on_disable,
                  bg="#f9e2af", fg="#1e1e2e", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=16, pady=6, cursor="hand2").pack(side="left", padx=(0, 8))

        # Skip Question button (blue) — only if question is optional
        if can_skip:
            def on_skip():
                result["action"] = "skip"
                win.destroy()

            tk.Button(btn_frame, text="⏭️ Skip Question", command=on_skip,
                      bg="#89b4fa", fg="#1e1e2e", font=("Segoe UI", 10, "bold"),
                      relief="flat", padx=16, pady=6, cursor="hand2").pack(side="left")

        # Handle window close as cancel
        win.protocol("WM_DELETE_WINDOW", on_cancel)

        # Focus the window
        win.focus_force()
        win.wait_window()  # Block until this Toplevel is destroyed

        return result["action"], result["answer"]

    def destroy(self):
        """Clean up the hidden root window."""
        try:
            self._root.destroy()
        except Exception:
            pass
