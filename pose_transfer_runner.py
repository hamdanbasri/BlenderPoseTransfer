import bpy
import os
import sys
import subprocess
import math

# --- Parse CLI args ---
argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []

pose_fbx = argv[0]
avatar_fbx = argv[1]
export_path = argv[2]
blender_exe = argv[3]
output_name = argv[4]  # No extension

export_file = os.path.join(export_path, f"{output_name}.fbx")
preview_image = os.path.join(export_path, f"{output_name}.png")
preview_script = os.path.join(export_path, "render_preview_temp.py")

# --- Clear scene ---
bpy.ops.wm.read_factory_settings(use_empty=True)

# --- Import avatar ---
bpy.ops.import_scene.fbx(filepath=avatar_fbx)
avatar_arm = [obj for obj in bpy.context.selected_objects if obj.type == 'ARMATURE']
if not avatar_arm:
    print("❌ No armature found in Avatar FBX.")
    sys.exit(1)
avatar = avatar_arm[0]

# --- Import pose ---
bpy.ops.import_scene.fbx(filepath=pose_fbx)
pose_arm = [obj for obj in bpy.context.selected_objects if obj.type == 'ARMATURE']
if not pose_arm:
    print("❌ No armature found in Pose FBX.")
    sys.exit(1)
pose = pose_arm[-1]

# --- Apply pose ---
bpy.context.view_layer.objects.active = avatar
bpy.ops.object.mode_set(mode='POSE')
for bone in avatar.pose.bones:
    if bone.name in pose.pose.bones:
        src = pose.pose.bones[bone.name]
        tgt = bone
        tgt.rotation_mode = 'QUATERNION'
        tgt.rotation_quaternion = src.rotation_quaternion
        if "hips" in bone.name.lower():
            tgt.location = src.location
bpy.ops.object.mode_set(mode='OBJECT')

# --- Bake pose ---
bpy.ops.nla.bake(
    frame_start=1,
    frame_end=1,
    only_selected=False,
    visual_keying=True,
    clear_constraints=False,
    use_current_action=True,
    bake_types={'POSE'}
)

# --- Delete pose rig ---
bpy.ops.object.select_all(action='DESELECT')
pose.select_set(True)
bpy.ops.object.delete()

# --- Clean custom props ---
def clear_custom_props(obj):
    for key in list(obj.keys()):
        if key not in '_RNA_UI':
            del obj[key]

clear_custom_props(avatar)
for child in avatar.children:
    if child.type == 'MESH':
        clear_custom_props(child)

# --- Export posed FBX ---
bpy.ops.object.select_all(action='DESELECT')
avatar.select_set(True)
for child in avatar.children:
    if child.type == 'MESH':
        child.select_set(True)

bpy.context.view_layer.objects.active = avatar
bpy.ops.export_scene.fbx(
    filepath=export_file,
    use_selection=True,
    apply_unit_scale=True,
    bake_anim=True,
    bake_anim_use_all_bones=True,
    bake_anim_use_nla_strips=False,
    add_leaf_bones=False
)

print(f"✅ Exported FBX: {export_file}")

# --- Write preview render script ---
with open(preview_script, "w") as f:
    f.write(f"""
import bpy
import math

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"{export_file}")

avatar = [obj for obj in bpy.context.selected_objects if obj.type == 'ARMATURE']
if not avatar:
    print("❌ No armature found in preview.")
    exit(1)
avatar = avatar[0]

# Add lighting
def add_light(name, type, loc, energy=1000):
    bpy.ops.object.light_add(type=type, location=loc)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    return light

add_light("Key", "AREA", (3, -3, 4), 1000)
add_light("Fill", "AREA", (-3, -2, 2), 500)
add_light("Back", "AREA", (0, 4, 3), 750)

# Add fixed camera
bpy.ops.object.camera_add(location=(0, -2.2, 0.9))
camera = bpy.context.object
camera.data.lens = 35
camera.rotation_euler = (math.radians(90), 0, 0)
bpy.context.scene.camera = camera

avatar.location = (0, 0, 0)

# Force update
bpy.context.view_layer.update()

# Render settings
scene = bpy.context.scene
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = True
scene.render.filepath = r"{preview_image}"
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024

# Ensure all images are loaded before rendering
for img in bpy.data.images:
    if img.packed_file is None and img.source == 'FILE':
        img.reload()

bpy.ops.render.render(write_still=True)
print("🖼️ Preview rendered to {preview_image}")
""")

# --- Run Blender subprocess to render preview ---
print("🚀 Running Blender subprocess for preview render...")
subprocess.run([
    blender_exe,
    "--background",
    "--python", preview_script
])

# --- Clean up ---
if os.path.exists(preview_script):
    os.remove(preview_script)
