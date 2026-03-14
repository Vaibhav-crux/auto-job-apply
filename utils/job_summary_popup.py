"""
Tkinter summary popup for job application completion.
Shows the final summary when application limit is reached.
"""

import tkinter as tk
from tkinter import ttk


class JobSummaryPopup:
    """Popup dialog to show job application summary."""

    def __init__(self):
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

    def show(self, summary_text):
        """
        Show a summary popup.

        Args:
            summary_text: The summary string to display

        Returns: None (blocks until OK clicked)
        """
        # Use Toplevel
        win = tk.Toplevel(self._root)
        win.title("Job Application Summary")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        # Window size and position
        window_width = 500
        window_height = 200
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        x = max((screen_width - window_width) // 2, 0)
        y = max((screen_height - window_height) // 2, 0)
        win.geometry(f"{window_width}x{window_height}+{x}+{y}")
        win.configure(bg="#1e1e2e")

        # Title
        title_label = ttk.Label(win, text="Application Complete!", style="Title.TLabel")
        title_label.pack(pady=(20, 10))

        # Summary text
        summary_label = ttk.Label(win, text=summary_text, style="TLabel", wraplength=450, justify="center")
        summary_label.pack(pady=(0, 20))

        # OK button
        def on_ok():
            win.destroy()

        ok_button = tk.Button(win, text="OK", command=on_ok,
                              bg="#a6e3a1", fg="#1e1e2e", font=("Segoe UI", 12, "bold"),
                              relief="flat", padx=20, pady=8, cursor="hand2")
        ok_button.pack()

        # Handle window close as OK
        win.protocol("WM_DELETE_WINDOW", on_ok)

        # Focus the window
        win.focus_force()
        win.wait_window()  # Block until this Toplevel is destroyed

    def destroy(self):
        """Clean up the hidden root window."""
        try:
            self._root.destroy()
        except Exception:
            pass
