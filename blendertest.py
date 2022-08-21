import os
import sys

sys.path.append(os.path.abspath("."))

import bpy
import plateaupy
import math

if True:
    # reset objects
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(True)
    # world
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[
        "Color"
    ].default_value = (0, 0, 0, 1)
    # lamp add
    bpy.ops.object.light_add(location=(0.0, 0.0, 2.0))
    # camera add
    bpy.ops.object.camera_add(location=(5.0, 0.0, 0.0))
    bpy.data.objects[bpy.data.cameras[-1].name].rotation_euler = (math.pi * 1 / 2, 0, math.pi * 1 / 2)

    # set view3d
    view3d = [x for x in bpy.data.screens["Layout"].areas if x.type == "VIEW_3D"][0]
    view3d.spaces[0].region_3d.view_perspective = "PERSP"
    view3d.spaces[0].shading.type = 'MATERIAL'
    view3d.spaces[0].lens = 50
    # view3d.spaces[0].clip_start = 100
    view3d.spaces[0].clip_end = 10000000

##################
#      args
##################
paths = ["CityGML2020/plateau-14100-yokohama-city-2020"]
cache = False
cachepath = "cached_blender"
kind = plateaupy.plobj.ALL
location = [
    53391540,
    53391541,
    53391530,
    53391531,
]
options = plateaupy.ploptions()
options.texturedir = cachepath
options.basemap = {"use": True, "layer": 0, "zoom": 18}
##################

# scan paths
pl = plateaupy.plparser(paths)

# load
# load multiple locations
for loc in location:
    pl.loadFiles(
        bLoadCache=cache, cachedir=cachepath, kind=kind, location=loc, options=options
    )

# decide the base point to show
vbase = None
targets = list(pl.dem.values())
if len(targets) > 0:
    vbase = targets[0].get_center_vertices()
targets = list(pl.bldg.values())
if vbase is None and len(targets) > 0:
    vbase = targets[0].get_center_vertices()
targets = list(pl.tran.values())
if vbase is None and len(targets) > 0:
    vbase = targets[0].get_center_vertices()
targets = list(pl.luse.values())
if vbase is None and len(targets) > 0:
    vbase = targets[0].get_center_vertices()

# show
pl.show_Blender_Objects(vbase=vbase)
