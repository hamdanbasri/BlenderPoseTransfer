import subprocess
import os
import threading
import platform
import json
import glob
import random
from datetime import datetime
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

class PoseTransferUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mixamo Pose Transfer")
        self.root.configure(bg="black")

        self.pose_fbx = tk.StringVar()
        self.avatar_fbx = tk.StringVar()
        self.export_folder = tk.StringVar()
        self.blender_exe = tk.StringVar()
        self.output_name = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready")
        self.exported_fbx_path = ""
        self.export_folder_path = ""
        self.preview_image = None

        self.settings_file = "settings.json"
        self.load_saved_paths()
        self._build_gui()
        self.animate_title()
        self.load_last_preview()

    def _build_gui(self):
        entry_style = {"bg": "#001100", "fg": "#00FF00", "insertbackground": "#00FF00"}
        label_style = {"bg": "black", "fg": "#00FF00", "font": ("Courier", 10, "bold")}
        button_style = {"bg": "#003300", "fg": "#00FF00", "activebackground": "#005500", "activeforeground": "#00FF00"}

        self.main_frame = tk.Frame(self.root, bg="black")
        self.main_frame.pack(fill="both", expand=True)

        self.left_frame = tk.Frame(self.main_frame, bg="black")
        self.left_frame.pack(side="left", padx=10, pady=10)

        # Animated Matrix title with glow
        self.title_text = "POSE TRANSFER"
        self.title_var = tk.StringVar(value=self.title_text)
        self.title_label = tk.Label(
            self.left_frame,
            textvariable=self.title_var,
            font=("Courier", 24, "bold"),
            fg="#00FF00",
            bg="black"
        )
        self.title_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 20))

        self.right_frame = tk.Frame(self.main_frame, bg="black", bd=2, relief="solid", width=256, height=256)
        self.right_frame.pack(side="right", padx=10, pady=10)
        self.right_frame.pack_propagate(False)

        self.preview_label = tk.Label(self.right_frame, text="waiting for render", bg="black", fg="#00FF00", font=("Courier", 12, "bold"))
        self.preview_label.pack(fill="both", expand=True)

        row = 1  # Skip title row

        def add_path_row(label, var, command=None, is_dnd=False):
            nonlocal row
            tk.Label(self.left_frame, text=label, **label_style).grid(row=row, column=0, sticky="e", padx=5, pady=5)
            entry = tk.Entry(self.left_frame, textvariable=var, width=60, **entry_style)
            entry.grid(row=row, column=1, padx=5, pady=5)
            if is_dnd:
                self.register_drag_drop(entry, var)
            if command:
                tk.Button(self.left_frame, text="Browse", command=command, **button_style).grid(row=row, column=2, padx=5, pady=5)
            row += 1

        add_path_row("Pose FBX:", self.pose_fbx, self.select_pose_fbx, is_dnd=True)
        add_path_row("Avatar FBX:", self.avatar_fbx, self.select_avatar_fbx, is_dnd=True)
        add_path_row("Export Folder:", self.export_folder, self.select_export_folder)
        add_path_row("Blender Executable:", self.blender_exe, self.select_blender_exe)
        add_path_row("Output Name (no .fbx):", self.output_name)

        self.loading_chars = ['⣾','⣽','⣻','⢿','⡿','⣟','⣯','⣷']
        self.loading_index = 0
        self.loading_label = tk.Label(self.left_frame, text="", font=("Courier", 18, "bold"), bg="black", fg="#00FF00")
        self.loading_label.grid(row=row, column=0, columnspan=3, pady=10)
        row += 1

        self.status_label = tk.Label(self.left_frame, textvariable=self.status_text, bg="black", fg="#00FF00", font=("Courier", 10, "bold"))
        self.status_label.grid(row=row, column=0, columnspan=3, pady=2)
        row += 1

        self.button_row = tk.Frame(self.left_frame, bg="black")
        self.button_row.grid(row=row, column=0, columnspan=3, pady=15)

        self.run_button = tk.Button(
            self.button_row, text="Run Pose Transfer", command=self.run_in_thread, width=20, font=("Courier", 10, "bold"), **button_style
        )
        self.run_button.pack(side="left", padx=5)

        self.view_folder_button = tk.Button(
            self.button_row, text="Open Export Folder", command=self.open_export_folder, width=20,
            font=("Courier", 10, "bold"), state=tk.DISABLED, **button_style
        )
        self.view_folder_button.pack(side="left", padx=5)
        row += 1

    def animate_title(self):
        def glitch():
            if random.random() < 0.9:
                text = ''.join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") if random.random() < 0.2 else c for c in self.title_text)
                self.title_var.set(text)
            else:
                self.title_var.set(self.title_text)
            self.root.after(100, glitch)
        glitch()

    def start_matrix_loading(self):
        self.loading_label.after(100, self._matrix_tick)

    def _matrix_tick(self):
        self.loading_label.config(text=self.loading_chars[self.loading_index % len(self.loading_chars)])
        self.loading_index += 1
        self.loading_anim = self.loading_label.after(100, self._matrix_tick)

    def stop_matrix_loading(self):
        if hasattr(self, 'loading_anim'):
            self.loading_label.after_cancel(self.loading_anim)
            self.loading_label.config(text="")

    def select_pose_fbx(self):
        file = filedialog.askopenfilename(title="Select Pose FBX", filetypes=[("FBX files", "*.fbx")])
        if file:
            self.pose_fbx.set(file)
            self.save_paths()

    def select_avatar_fbx(self):
        file = filedialog.askopenfilename(title="Select Avatar FBX", filetypes=[("FBX files", "*.fbx")])
        if file:
            self.avatar_fbx.set(file)
            self.save_paths()

    def select_export_folder(self):
        folder = filedialog.askdirectory(title="Select Export Folder")
        if folder:
            self.export_folder.set(folder)
            self.save_paths()

    def select_blender_exe(self):
        exe = filedialog.askopenfilename(title="Select Blender Executable", filetypes=[("Executable", "*.exe" if os.name == 'nt' else "*")])
        if exe:
            self.blender_exe.set(exe)
            self.save_paths()

    def register_drag_drop(self, entry_widget, target_var):
        def drop(event):
            path = event.data.strip().strip("{}")
            if path.lower().endswith(".fbx"):
                target_var.set(path)
                self.save_paths()
        entry_widget.drop_target_register(DND_FILES)
        entry_widget.dnd_bind('<<Drop>>', drop)

    def load_saved_paths(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                    self.pose_fbx.set(data.get("pose_fbx", ""))
                    self.avatar_fbx.set(data.get("avatar_fbx", ""))
                    self.export_folder.set(data.get("export_folder", ""))
                    self.blender_exe.set(data.get("blender_exe", ""))
                    self.output_name.set(data.get("output_name", "posed_avatar"))
            except Exception as e:
                print("Failed to load settings:", e)

    def save_paths(self):
        data = {
            "pose_fbx": self.pose_fbx.get(),
            "avatar_fbx": self.avatar_fbx.get(),
            "export_folder": self.export_folder.get(),
            "blender_exe": self.blender_exe.get(),
            "output_name": self.output_name.get()
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print("Failed to save settings:", e)

    def run_in_thread(self):
        thread = threading.Thread(target=self.run_pose_transfer)
        thread.start()

    def run_pose_transfer(self):
        self.status_text.set("Running pose transfer...")
        self.view_folder_button.config(state=tk.DISABLED)
        self.start_matrix_loading()

        pose = self.pose_fbx.get()
        avatar = self.avatar_fbx.get()
        export = self.export_folder.get()
        blender = self.blender_exe.get()
        name = self.output_name.get().strip()

        if not all([pose, avatar, export, blender, name]):
            self.status_text.set("Please fill in all fields.")
            self.stop_matrix_loading()
            return

        self.exported_fbx_path = os.path.join(export, f"{name}.fbx")
        self.export_folder_path = export
        preview_img_path = os.path.join(export, f"{name}.png")
        script_path = os.path.abspath("pose_transfer_runner.py")

        cmd = [blender, "--background", "--python", script_path, "--", pose, avatar, export, blender, name]

        try:
            subprocess.run(cmd, check=True)
            completion_time = datetime.now().strftime("%H:%M:%S")
            self.status_text.set(f"\u2705 Pose transfer complete! [{completion_time}]")
            self.load_preview_image(preview_img_path)
            self.view_folder_button.config(state=tk.NORMAL)
        except subprocess.CalledProcessError:
            self.status_text.set("\u274C Blender failed to run. Check console output.")
        finally:
            self.stop_matrix_loading()

    def load_preview_image(self, path):
        if os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA").resize((256, 256))
                self.preview_image = ImageTk.PhotoImage(img)
                self.preview_label.config(image=self.preview_image, text="")
            except Exception as e:
                print("Failed to load preview image:", e)
        else:
            self.preview_label.config(image="", text="waiting for render")

    def load_last_preview(self):
        export_dir = self.export_folder.get()
        if export_dir:
            previews = sorted(glob.glob(os.path.join(export_dir, "*.png")), key=os.path.getmtime, reverse=True)
            if previews:
                self.load_preview_image(previews[0])

    def open_export_folder(self):
        if os.path.exists(self.export_folder_path):
            try:
                if platform.system() == "Windows":
                    os.startfile(self.export_folder_path)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", self.export_folder_path])
                else:
                    subprocess.run(["xdg-open", self.export_folder_path])
            except Exception as e:
                print("Could not open folder:", e)
        else:
            self.status_text.set("\u274C Export folder not found.")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = PoseTransferUI(root)
    root.mainloop()
