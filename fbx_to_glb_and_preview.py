import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import tempfile
import webbrowser
import base64
import threading

class FBXViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FBX → GLB Previewer")

        self.fbx_path = tk.StringVar()
        self.blender_path = tk.StringVar()

        self._build_gui()

    def _build_gui(self):
        row = 0

        def add_row(label, var, browse_fn):
            nonlocal row
            tk.Label(self.root, text=label).grid(row=row, column=0, sticky='e', padx=5, pady=5)
            tk.Entry(self.root, textvariable=var, width=60).grid(row=row, column=1, padx=5, pady=5)
            tk.Button(self.root, text="Browse", command=browse_fn).grid(row=row, column=2, padx=5, pady=5)
            row += 1

        add_row("FBX File:", self.fbx_path, self.select_fbx)
        add_row("Blender Executable:", self.blender_path, self.select_blender)

        tk.Button(self.root, text="Convert & Preview", command=self.run_conversion, width=30, bg="#2196F3", fg="white").grid(row=row, column=0, columnspan=3, pady=15)

    def select_fbx(self):
        file = filedialog.askopenfilename(title="Select FBX", filetypes=[("FBX Files", "*.fbx")])
        if file:
            self.fbx_path.set(file)

    def select_blender(self):
        exe = filedialog.askopenfilename(title="Select Blender Executable", filetypes=[("Executable", "*.exe" if os.name == 'nt' else "*")])
        if exe:
            self.blender_path.set(exe)

    def run_conversion(self):
        threading.Thread(target=self._convert_and_preview).start()

    def _convert_and_preview(self):
        fbx = self.fbx_path.get()
        blender = self.blender_path.get()

        if not all([fbx, blender]):
            messagebox.showerror("Missing Info", "Please select both FBX and Blender executable.")
            return

        tmp_dir = tempfile.mkdtemp()
        glb_path = os.path.join(tmp_dir, "model.glb")
        blender_script = os.path.join(tmp_dir, "convert.py")

        # Write Blender script
        with open(blender_script, "w") as f:
            f.write(f"""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"{fbx}")
bpy.ops.export_scene.gltf(filepath=r"{glb_path}", export_format='GLB', export_yup=True)
bpy.ops.wm.quit_blender()
""")

        # Run Blender
        try:
            subprocess.run([blender, "--background", "--python", blender_script], check=True)
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Blender failed:\n{e}")
            return

        # Read GLB and encode as base64
        with open(glb_path, "rb") as f:
            glb_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Create HTML viewer
        html_path = os.path.join(tmp_dir, "viewer.html")
        with open(html_path, "w") as f:
            f.write(self._build_html_viewer(glb_b64))

        webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")

    def _build_html_viewer(self, glb_b64):
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GLB Viewer</title>
    <style>body {{ margin: 0; overflow: hidden; }}</style>
</head>
<body>
<script type="module">
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.module.js";
import {{ OrbitControls }} from "https://cdn.jsdelivr.net/npm/three@0.158.0/examples/jsm/controls/OrbitControls.js";
import {{ GLTFLoader }} from "https://cdn.jsdelivr.net/npm/three@0.158.0/examples/jsm/loaders/GLTFLoader.js";

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf0f0f0);
const camera = new THREE.PerspectiveCamera(70, window.innerWidth/window.innerHeight, 0.1, 1000);
camera.position.set(0, 1.5, 3);

const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

const light1 = new THREE.HemisphereLight(0xffffff, 0x444444, 1.2);
scene.add(light1);

const loader = new GLTFLoader();
const b64 = "{glb_b64}";
const arrayBuffer = Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer;

loader.parse(arrayBuffer, '', gltf => {{
    scene.add(gltf.scene);
}}, console.error);

function animate() {{
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}}
animate();

window.addEventListener('resize', () => {{
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}});
</script>
</body>
</html>
"""

# Run it
if __name__ == "__main__":
    root = tk.Tk()
    app = FBXViewerApp(root)
    root.mainloop()
