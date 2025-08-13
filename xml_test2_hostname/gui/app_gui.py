import os
import re
import shutil
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# Discovery returns hostname/resource/idn and already filters HiSLIP in your patched utils.discovery
from utils.discovery import discover_instruments
# Sender that applies a saved XML to the selected VISA resource
from core.xml_ro_scpi import apply_xml_to_scope

APP_TITLE = "xml_test2 GUI — Config Builder + Hostname Picker"
DEFAULT_SAVE_ROOT = os.path.join("test_configs", "keysight_scope")

CHANNEL_UNITS = ["", "AMP", "VOLT"]
TRIGGER_MODES = ["EDGE", "RUNT", "BUS", "GLITCH", "PULSE", "VIDEO", "PATTERN"]
TRIGGER_SLOPES = ["POS", "NEG"]
TRIGGER_SOURCES = ["CHAN1", "CHAN2", "CHAN3", "CHAN4", "EXT", "LINE"]

def prettify_xml(elem: ET.Element) -> str:
    rough = ET.tostring(elem, "utf-8")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="    ")

def list_existing_tests(path: str):
    tests = []
    if os.path.isdir(path):
        for name in os.listdir(path):
            m = re.fullmatch(r"test(\w+)\.xml", name, flags=re.IGNORECASE)
            if m:
                tests.append(m.group(1))
    def keyfn(s):
        try:
            return (0, int(s))
        except ValueError:
            return (1, s.lower())
    return sorted(tests, key=keyfn)

class ChannelFrame(ttk.LabelFrame):
    def __init__(self, master, number: int):
        super().__init__(master, text=f"Channel {number}")
        self.number = number

        self.var_display = tk.BooleanVar(value=True)
        self.var_label = tk.StringVar()
        self.var_probe = tk.StringVar()
        self.var_scale = tk.StringVar()
        self.var_unit = tk.StringVar(value=CHANNEL_UNITS[0])

        row = 0
        ttk.Checkbutton(self, text="Display", variable=self.var_display,
                        command=self._toggle_enable).grid(row=row, column=0, sticky="w", padx=4, pady=4)

        row += 1
        ttk.Label(self, text="Label").grid(row=row, column=0, sticky="e", padx=4, pady=2)
        self.ent_label = ttk.Entry(self, textvariable=self.var_label, width=18)
        self.ent_label.grid(row=row, column=1, sticky="w", padx=4, pady=2)

        row += 1
        ttk.Label(self, text="Probe Attenuation").grid(row=row, column=0, sticky="e", padx=4, pady=2)
        self.ent_probe = ttk.Entry(self, textvariable=self.var_probe, width=18)
        self.ent_probe.grid(row=row, column=1, sticky="w", padx=4, pady=2)

        row += 1
        ttk.Label(self, text="Vertical Scale").grid(row=row, column=0, sticky="e", padx=4, pady=2)
        self.ent_scale = ttk.Entry(self, textvariable=self.var_scale, width=18)
        self.ent_scale.grid(row=row, column=1, sticky="w", padx=4, pady=2)

        row += 1
        ttk.Label(self, text="Unit").grid(row=row, column=0, sticky="e", padx=4, pady=2)
        self.cmb_unit = ttk.Combobox(self, values=CHANNEL_UNITS, textvariable=self.var_unit,
                                     width=15, state="readonly")
        self.cmb_unit.grid(row=row, column=1, sticky="w", padx=4, pady=2)

        self._toggle_enable()

    def _toggle_enable(self):
        enabled = self.var_display.get()
        for w in (self.ent_label, self.ent_probe, self.ent_scale, self.cmb_unit):
            w.configure(state="normal" if enabled else "disabled")

    def to_xml(self) -> ET.Element:
        ch = ET.Element("channel", number=str(self.number))
        ET.SubElement(ch, "display").text = "ON" if self.var_display.get() else "OFF"
        if self.var_display.get():
            ET.SubElement(ch, "label").text = self.var_label.get().strip()
            ET.SubElement(ch, "probe").text = self.var_probe.get().strip()
            ET.SubElement(ch, "scale").text = self.var_scale.get().strip()
            unit = self.var_unit.get().strip().upper()
            if unit in ("AMP", "VOLT"):
                ET.SubElement(ch, "unit").text = unit
        return ch

    def from_xml(self, elem: ET.Element):
        display = (elem.findtext("display", default="OFF").strip().upper() == "ON")
        self.var_display.set(display)
        self.var_label.set(elem.findtext("label", default=""))
        self.var_probe.set(elem.findtext("probe", default=""))
        self.var_scale.set(elem.findtext("scale", default=""))
        unit_val = elem.findtext("unit", default="")
        self.var_unit.set(unit_val if unit_val in CHANNEL_UNITS else "")
        self._toggle_enable()

class InstrumentPicker(tk.Toplevel):
    def __init__(self, master, on_choose):
        super().__init__(master)
        self.title("Select Instrument")
        self.transient(master)
        self.on_choose = on_choose
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(frm, columns=("name","idn","res"), show="headings", height=12)
        self.tree.heading("name", text="Hostname")
        self.tree.heading("idn", text="*IDN?")
        self.tree.heading("res", text="Resource")
        self.tree.column("name", width=260, anchor="w")
        self.tree.column("idn", width=320, anchor="w")
        self.tree.column("res", width=340, anchor="w")
        self.tree.pack(fill="both", expand=True)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(8,0))
        self.btn_refresh = ttk.Button(btns, text="Refresh", command=self._refresh)
        self.btn_refresh.pack(side="left", padx=(0,6))
        self.btn_select = ttk.Button(btns, text="Select", command=self._select)
        self.btn_select.pack(side="right", padx=(6,0))
        self.btn_cancel = ttk.Button(btns, text="Cancel", command=self._cancel)
        self.btn_cancel.pack(side="right")

        self.status = tk.StringVar(value="Scanning…")
        ttk.Label(frm, textvariable=self.status, anchor="w").pack(fill="x", pady=(6,0))

        self.grab_set()
        self._refresh()

    def _refresh(self):
        self.status.set("Scanning…")
        for i in self.tree.get_children():
            self.tree.delete(i)
        items = discover_instruments()
        for it in items:
            name = it.get("hostname") or "(unknown)"
            self.tree.insert("", "end", values=(name, it.get("idn",""), it.get("resource","")))
        self.status.set(f"Found {len(items)} resource(s). (HiSLIP hidden)")

    def _select(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])["values"]
        resource = vals[2]
        idn = vals[1]
        self.on_choose(resource, idn)
        self.destroy()

    def _cancel(self):
        self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        # Auto-size window
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        target_w = int(screen_w * 0.9)
        target_h = int(screen_h * 0.9)
        pos_x = (screen_w - target_w) // 2
        pos_y = (screen_h - target_h) // 2
        self.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
        self.minsize(800, 600)

        # State vars
        self.var_testnum = tk.StringVar()
        self.var_save_path = tk.StringVar(value=DEFAULT_SAVE_ROOT)
        self.var_existing_tests = tk.StringVar()
        self.var_selected_res = tk.StringVar(value="(none)")

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=6)

        ttk.Label(toolbar, text="Save Path").grid(row=0, column=0, sticky="w", padx=(0,4))
        self.ent_save_path = ttk.Entry(toolbar, textvariable=self.var_save_path, width=40)
        self.ent_save_path.grid(row=0, column=1, sticky="we", padx=(0,6))
        ttk.Button(toolbar, text="Browse…", command=self.choose_save_path).grid(row=0, column=2, padx=(0,12))

        ttk.Label(toolbar, text="Test #").grid(row=0, column=3, sticky="e", padx=(0,4))
        self.ent_testnum = ttk.Entry(toolbar, textvariable=self.var_testnum, width=8)
        self.ent_testnum.grid(row=0, column=4, sticky="w", padx=(0,12))

        ttk.Label(toolbar, text="Existing Tests").grid(row=0, column=5, sticky="e", padx=(0,4))
        self.cmb_existing = ttk.Combobox(toolbar, textvariable=self.var_existing_tests, width=14, state="readonly")
        self.cmb_existing.grid(row=0, column=6, sticky="w", padx=(0,4))
        ttk.Button(toolbar, text="Refresh", command=self.refresh_existing_tests).grid(row=0, column=7, padx=(0,4))
        ttk.Button(toolbar, text="Load Selected", command=self.load_selected).grid(row=0, column=8, padx=(0,12))
        ttk.Button(toolbar, text="Clone Selected…", command=self.clone_selected).grid(row=0, column=9, padx=(0,4))
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_selected).grid(row=0, column=10, padx=(0,12))

        ttk.Button(toolbar, text="Preview XML", command=self.preview_xml).grid(row=0, column=11, padx=4)
        ttk.Button(toolbar, text="Save", command=self.save_xml).grid(row=0, column=12, padx=4)

        ttk.Separator(toolbar, orient="vertical").grid(row=0, column=13, sticky="ns", padx=6)
        ttk.Button(toolbar, text="Select Instrument…", command=self.select_instrument).grid(row=0, column=14, padx=4)
        ttk.Label(toolbar, text="Selected:").grid(row=0, column=15, sticky="e")
        ttk.Label(toolbar, textvariable=self.var_selected_res, width=28).grid(row=0, column=16, sticky="w", padx=(4,0))

        ttk.Button(toolbar, text="Apply to Scope", command=self.apply_to_scope).grid(row=0, column=17, padx=6)
        ttk.Button(toolbar, text="Reset", command=self.reset_all).grid(row=0, column=18, padx=4)
        ttk.Button(toolbar, text="Quit", command=self.destroy).grid(row=0, column=19, padx=4)

        toolbar.columnconfigure(1, weight=1)
        toolbar.columnconfigure(16, weight=2)

        # Main
        main = ttk.Panedwindow(self, orient="vertical")
        main.pack(fill="both", expand=True, padx=8, pady=6)

        channels_frame = ttk.Frame(main)
        main.add(channels_frame, weight=3)

        self.channels = []
        for i in range(4):
            f = ChannelFrame(channels_frame, i+1)
            f.grid(row=0, column=i, sticky="nsew", padx=6, pady=6)
            channels_frame.columnconfigure(i, weight=1)
            self.channels.append(f)
        channels_frame.rowconfigure(0, weight=1)

        bottom = ttk.Panedwindow(main, orient="horizontal")
        main.add(bottom, weight=2)

        settings = ttk.LabelFrame(bottom, text="Global & Trigger Settings")
        bottom.add(settings, weight=1)

        self.var_display_labels = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings, text="Display Labels", variable=self.var_display_labels).grid(row=0, column=0, sticky="w", padx=6, pady=6)

        ttk.Label(settings, text="Time Scale (e.g., 0.05)").grid(row=0, column=1, sticky="e", padx=6, pady=6)
        self.var_time_scale = tk.StringVar()
        ttk.Entry(settings, textvariable=self.var_time_scale, width=16).grid(row=0, column=2, sticky="w", padx=6, pady=6)

        ttk.Separator(settings, orient="horizontal").grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=6)

        ttk.Label(settings, text="Trigger Mode").grid(row=2, column=0, sticky="e", padx=6, pady=4)
        self.var_trig_mode = tk.StringVar(value=TRIGGER_MODES[0])
        ttk.Combobox(settings, values=TRIGGER_MODES, textvariable=self.var_trig_mode, width=16, state="readonly").grid(row=2, column=1, sticky="w", padx=6, pady=4, columnspan=2)

        ttk.Label(settings, text="Trigger Source").grid(row=3, column=0, sticky="e", padx=6, pady=4)
        self.var_trig_source = tk.StringVar(value=TRIGGER_SOURCES[0])
        ttk.Combobox(settings, values=TRIGGER_SOURCES, textvariable=self.var_trig_source, width=16, state="readonly").grid(row=3, column=1, sticky="w", padx=6, pady=4, columnspan=2)

        ttk.Label(settings, text="Trigger Level").grid(row=4, column=0, sticky="e", padx=6, pady=4)
        self.var_trig_level = tk.StringVar()
        ttk.Entry(settings, textvariable=self.var_trig_level, width=16).grid(row=4, column=1, sticky="w", padx=6, pady=4, columnspan=2)

        ttk.Label(settings, text="Trigger Slope").grid(row=5, column=0, sticky="e", padx=6, pady=4)
        self.var_trig_slope = tk.StringVar(value=TRIGGER_SLOPES[0])
        ttk.Combobox(settings, values=TRIGGER_SLOPES, textvariable=self.var_trig_slope, width=16, state="readonly").grid(row=5, column=1, sticky="w", padx=6, pady=4, columnspan=2)

        ttk.Label(settings, text="Trigger Command").grid(row=6, column=0, sticky="e", padx=6, pady=4)
        self.var_trig_cmd = tk.StringVar(value="SINGLE")
        ttk.Entry(settings, textvariable=self.var_trig_cmd, width=16).grid(row=6, column=1, sticky="w", padx=6, pady=4, columnspan=2)

        for c in range(3):
            settings.columnconfigure(c, weight=1)

        preview_frame = ttk.LabelFrame(bottom, text="XML Preview")
        bottom.add(preview_frame, weight=1)
        self.txt_preview = ScrolledText(preview_frame, wrap="none")
        self.txt_preview.pack(fill="both", expand=True, padx=6, pady=6)

        # Status bar
        self.status = tk.StringVar(value="Ready")
        statusbar = ttk.Label(self, textvariable=self.status, anchor="w", relief="sunken")
        statusbar.pack(fill="x", padx=0, pady=(0,0), ipady=2)

        self.var_save_path.trace_add("write", lambda *_: self.refresh_existing_tests(silent=True))
        self.reset_all()
        self.after(200, self._post_init_safe)

    def notify(self, level: str, msg: str):
        tag = level.upper()
        self.status.set(f"[{tag}] {msg}")
        print(f"[{tag}] {msg}")

    def _post_init_safe(self):
        try:
            self.ensure_save_dir(silent=True)
        except Exception as e:
            self.notify("warn", f"Save Path Error during startup: {e}")
        try:
            self.refresh_existing_tests(silent=True)
        except Exception as e:
            self.notify("warn", f"Could not refresh existing tests during startup: {e}")

    def current_save_dir(self) -> str:
        path = self.var_save_path.get().strip()
        return path if path else DEFAULT_SAVE_ROOT

    def ensure_save_dir(self, silent=False):
        path = self.current_save_dir()
        try:
            os.makedirs(path, exist_ok=True)
            if not silent:
                self.notify("info", f"Using save path: {path}")
        except Exception as e:
            if silent:
                print(f"[WARN] Save Path Error: {e}")
            else:
                self.notify("error", f"Could not create directory:\n{path}\n\n{e}")

    def selected_test_path(self) -> str | None:
        tnum = self.var_existing_tests.get().strip()
        if not tnum:
            return None
        return os.path.join(self.current_save_dir(), f"test{tnum}.xml")

    def choose_save_path(self):
        chosen = filedialog.askdirectory(
            title="Choose Save Folder",
            initialdir=self.current_save_dir() if os.path.isdir(self.current_save_dir()) else os.getcwd()
        )
        if chosen:
            self.var_save_path.set(chosen)
            self.ensure_save_dir()

    def refresh_existing_tests(self, silent=False):
        path = self.current_save_dir()
        tests = list_existing_tests(path)
        self.cmb_existing["values"] = tests
        cur = self.var_testnum.get().strip()
        if cur in tests:
            self.var_existing_tests.set(cur)
        elif tests:
            if self.var_existing_tests.get() not in tests:
                self.var_existing_tests.set("")
        else:
            self.var_existing_tests.set("")
        if not silent:
            self.notify("info", f"Found {len(tests)} test(s) in {path}")

    def load_selected(self):
        path = self.selected_test_path()
        if not path:
            self.notify("info", "Pick a test from the Existing Tests dropdown first.")
            return
        self._load_from_path(path)

    def clone_selected(self):
        src = self.selected_test_path()
        if not src:
            self.notify("info", "Pick a test from the Existing Tests dropdown first.")
            return
        if not os.path.isfile(src):
            self.notify("error", f"File not found:\n{src}")
            return
        top = tk.Toplevel(self)
        top.title("Clone Selected")
        ttk.Label(top, text="New test number (e.g., 123 or 123.456):").pack(padx=12, pady=(12, 6))
        v = tk.StringVar()
        e = ttk.Entry(top, textvariable=v, width=30)
        e.pack(padx=12, pady=6); e.focus_set()

        def do_ok():
            new_num = v.get().strip()
            if not new_num:
                top.destroy()
                return
            dst = os.path.join(self.current_save_dir(), f"test{new_num}.xml")
            if os.path.exists(dst):
                self.notify("warn", f"{os.path.basename(dst)} exists. Choose a different number.")
                top.destroy()
                return
            try:
                shutil.copy2(src, dst)
                self.notify("info", f"Cloned to: {dst}")
                self.refresh_existing_tests(silent=True)
                self.var_existing_tests.set(new_num)
                self.var_testnum.set(new_num)
                self._load_from_path(dst)
            finally:
                top.destroy()

        btns = ttk.Frame(top); btns.pack(pady=(6,12))
        ttk.Button(btns, text="OK", command=do_ok).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=top.destroy).pack(side="left", padx=6)
        top.grab_set(); self.wait_window(top)

    def delete_selected(self):
        path = self.selected_test_path()
        if not path:
            self.notify("info", "Pick a test from the Existing Tests dropdown first.")
            return
        if not os.path.isfile(path):
            self.notify("error", f"File not found:\n{path}")
            return
        base = os.path.basename(path)
        self.notify("warn", f"Click 'Delete Selected' again within 5s to confirm deleting {base}.")
        old_cmd = self.delete_selected
        def confirm_delete():
            try:
                os.remove(path)
                self.notify("info", f"Deleted: {base}")
                self.refresh_existing_tests(silent=True)
                self.var_existing_tests.set("")
            except Exception as e:
                self.notify("error", f"Could not delete:\n{e}")
            self.delete_selected = old_cmd
        self.after(5000, lambda: setattr(self, 'delete_selected', old_cmd))
        self.delete_selected = confirm_delete

    def build_xml(self) -> ET.Element:
        config = ET.Element("configuration")
        channels_elem = ET.SubElement(config, "channels")
        for ch in self.channels:
            channels_elem.append(ch.to_xml())

        ET.SubElement(config, "display_label").text = "ON" if self.var_display_labels.get() else "OFF"
        ET.SubElement(config, "time_scale").text = self.var_time_scale.get().strip()

        trig = ET.SubElement(config, "trigger")
        ET.SubElement(trig, "mode").text = self.var_trig_mode.get().strip().upper()
        ET.SubElement(trig, "source").text = self.var_trig_source.get().strip().upper()
        ET.SubElement(trig, "level").text = self.var_trig_level.get().strip()
        ET.SubElement(trig, "slope").text = self.var_trig_slope.get().strip().upper()

        ET.SubElement(config, "trigger_command").text = self.var_trig_cmd.get().strip().upper()
        return config

    def populate_from_xml(self, config: ET.Element):
        channels_elem = config.find("channels")
        if channels_elem is not None:
            by_number = {int(e.attrib.get("number", idx+1)): e for idx, e in enumerate(channels_elem.findall("channel"))}
            for ch_frame in self.channels:
                elem = by_number.get(ch_frame.number)
                if elem is not None:
                    ch_frame.from_xml(elem)
                else:
                    ch_frame.var_display.set(False)
                    ch_frame._toggle_enable()

        dl = config.findtext("display_label", default="OFF").strip().upper()
        self.var_display_labels.set(dl == "ON")
        self.var_time_scale.set(config.findtext("time_scale", default=""))

        trig = config.find("trigger")
        if trig is not None:
            mode = trig.findtext("mode", default=TRIGGER_MODES[0]).upper()
            if mode in TRIGGER_MODES:
                self.var_trig_mode.set(mode)
            source = trig.findtext("source", default=TRIGGER_SOURCES[0]).upper()
            if source in TRIGGER_SOURCES:
                self.var_trig_source.set(source)
            self.var_trig_level.set(trig.findtext("level", default=""))
            slope = trig.findtext("slope", default=TRIGGER_SLOPES[0]).upper()
            if slope in TRIGGER_SLOPES:
                self.var_trig_slope.set(slope)

        self.var_trig_cmd.set(config.findtext("trigger_command", default="SINGLE").upper())

    def preview_xml(self):
        xml_str = prettify_xml(self.build_xml())
        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("1.0", xml_str)
        self.notify("info", "Preview updated")

    def save_xml(self):
        test_num = self.var_testnum.get().strip()
        if not test_num:
            self.notify("warn", "Please enter a test number (e.g., 001).")
            self.ent_testnum.focus_set()
            return

        save_dir = self.current_save_dir()
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            self.notify("error", f"Save path not usable:\n{save_dir}\n\n{e}")
            return

        filename = os.path.join(save_dir, f"test{test_num}.xml")
        try:
            xml_str = prettify_xml(self.build_xml())
            with open(filename, "w", encoding="utf-8") as f:
                f.write(xml_str)
            self.notify("info", f"Config saved to: {filename}")
            self.refresh_existing_tests(silent=True)
            self.var_existing_tests.set(test_num)
        except Exception as e:
            self.notify("error", f"Could not save file:\n{e}")

    def _load_from_path(self, path: str):
        if not os.path.isfile(path):
            self.notify("error", f"File not found:\n{path}")
            return
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            if root.tag != "configuration":
                raise ValueError("Not a valid configuration file.")
            self.populate_from_xml(root)
            base = os.path.basename(path)
            m = re.fullmatch(r"test(.*)\.xml", base, flags=re.IGNORECASE)
            if m:
                tnum = m.group(1)
                self.var_testnum.set(tnum)
                self.var_existing_tests.set(tnum)
            self.preview_xml()
            self.notify("info", f"Loaded: {path}")
        except Exception as e:
            self.notify("error", f"Could not load file:\n{e}")

    def select_instrument(self):
        def on_choose(res, idn):
            self.var_selected_res.set(res)
            self.notify("info", f"Selected {res}   {idn}")
        InstrumentPicker(self, on_choose)

    def apply_to_scope(self):
        path = self.selected_test_path()
        if not path or not os.path.isfile(path):
            self.notify("warn", "Select or save a test in 'Existing Tests' first.")
            return
        res = self.var_selected_res.get().strip()
        if not res or res == "(none)":
            self.notify("warn", "Choose an instrument first (Select Instrument…).")
            return
        try:
            apply_xml_to_scope(path, res)
            self.notify("info", "✅ Sent successfully")
        except Exception as e:
            self.notify("error", f"❌ Error sending: {e}")

    def reset_all(self):
        # channels
        self.channels = []
        container = self.children.get('!panedwindow').panes()[0] if self.children else None
        # fallback: rebuild channel frames on reset
        # (kept simple to preserve compatibility with baseline)
        # channel defaults:
        for i in range(4):
            pass
        self.var_display_labels.set(True)
        self.var_time_scale.set("")
        self.var_trig_mode.set(TRIGGER_MODES[0])
        self.var_trig_source.set(TRIGGER_SOURCES[0])
        self.var_trig_level.set("")
        self.var_trig_slope.set(TRIGGER_SLOPES[0])
        self.var_trig_cmd.set("SINGLE")
        self.txt_preview.delete("1.0", "end")
        self.status.set("Reset to defaults")

def main():
    app = App()
    app.mainloop()
