# Godot test project for pix_parallax (Godot 4.7)
1. `python gizpix.py pix_parallax draw --preset dusk_hills --out tmp/dusk_hills`
2. `python gizpix.py pix_parallax export tmp/dusk_hills/stack.json --godot parallax/godot_test/bg/dusk_hills --res-dir res://bg/dusk_hills --mode camera`
3. `godot --headless --import --path parallax/godot_test`, then `godot --path parallax/godot_test -- scene=dusk_hills only=clouds frames=16 speed=2 out=j`
   (user args: scene, only=<layer>, frames, speed / speedy=<camera px per frame in x / y>, zoom, smooth=0|1, log=1 (prints layer positions and delta), out=<prefix>). It writes out_001.png ... (320x180). A shift of the layer between frames
   shows the step per frame (1,0,0,0 = stutter). Keep `2d/snap/snap_2d_transforms_to_pixel=true` in project.godot to test the whole-pixel case.
The exported scene file must be named like its folder (`bg/NAME/NAME.tscn`); rename if you export under another folder name.
`main_r.tscn` (run with `godot --path . res://main_r.tscn -- scene=NAME only=LAYER mode=plain|godot|lerp|round speed=8 out=cr`) compares camera policies: plain, Camera2D smoothing (godot), own lerp smoothing, and own smoothing rounded to whole pixels.
