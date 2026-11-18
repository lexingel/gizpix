extends Node2D
# camera policy test. user args: scene, only, frames, speed (camera px/frame), mode: godot (Camera2D smoothing) | lerp (own smoothing, unrounded) | round (own smoothing, camera rounded to whole pixels) | plain (no smoothing)
var cam: Camera2D
var f := 0
var a := {"only": "", "frames": "90", "speed": "8", "scene": "art_dusk", "mode": "plain", "out": "pr"}
var layers: Node
var target := 0.0
var s := 0.0
func _ready():
	for q in OS.get_cmdline_user_args():
		var kv = q.split("=")
		a[kv[0]] = kv[1]
	layers = load("res://bg/%s/%s.tscn" % [a.scene, a.scene]).instantiate()
	add_child(layers)
	cam = Camera2D.new()
	cam.anchor_mode = Camera2D.ANCHOR_MODE_FIXED_TOP_LEFT
	cam.position_smoothing_enabled = a.mode == "godot"
	cam.position_smoothing_speed = 5.0
	add_child(cam)
	if a.only != "":
		for n in layers.get_children():
			n.visible = (n.name == a.only)
func _process(_d):
	f += 1
	target += float(a.speed)
	if a.mode == "godot" or a.mode == "plain":
		cam.position.x = target
	elif a.mode == "lerp":
		s += (target - s) * 0.2
		cam.position.x = s
	else:
		s += (target - s) * 0.2
		cam.position.x = round(s)
	if f > 2:
		get_viewport().get_texture().get_image().save_png("res://%s_%03d.png" % [a.out, f - 2])
	if f >= int(a.frames) + 2:
		get_tree().quit(0)
