extends Node2D
# user args (key=value): scene only frames speed(cam px/frame in x) speedy(cam px/frame in y) zoom smooth(0/1) log(0/1) out(prefix, empty = no shots)
var cam: Camera2D
var f := 0
var a := {"only": "", "frames": "16", "speed": "2", "speedy": "0", "zoom": "1", "out": "", "scene": "dusk_hills", "smooth": "0", "log": "0"}
var layers: Node
var t0 := 0
func _ready():
	for s in OS.get_cmdline_user_args():
		var kv = s.split("=")
		a[kv[0]] = kv[1]
	var packed = load("res://bg/%s/%s.tscn" % [a.scene, a.scene])
	layers = packed.instantiate()
	add_child(layers)
	cam = Camera2D.new()
	cam.anchor_mode = Camera2D.ANCHOR_MODE_FIXED_TOP_LEFT
	cam.position_smoothing_enabled = a.smooth == "1"
	cam.zoom = Vector2(float(a.zoom), float(a.zoom))
	add_child(cam)
	if a.only != "":
		for n in layers.get_children():
			n.visible = (n.name == a.only)
	t0 = Time.get_ticks_usec()
func _process(delta):
	f += 1
	cam.position.x += float(a.speed)
	cam.position.y += float(a.speedy)
	if a.log == "1":
		var n = layers.get_node(a.only if a.only != "" else "hills")
		print("LOG f=%d t=%.4f delta=%.5f cam=%.2f,%.2f layer=%.3f,%.3f" % [f, (Time.get_ticks_usec() - t0) / 1e6, delta, cam.position.x, cam.position.y, n.get_node("Sprite2D").global_position.x, n.get_node("Sprite2D").global_position.y])
	if a.out != "" and f > 2:
		get_viewport().get_texture().get_image().save_png("res://%s_%03d.png" % [a.out, f - 2])
	if f >= int(a.frames) + 2:
		get_tree().quit(0)
