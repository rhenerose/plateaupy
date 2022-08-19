from plateaupy.plobj import plobj,plmesh
from plateaupy.plutils import *
from plateaupy.ploptions import ploptions
import numpy as np
import copy
import os
from lxml import etree

class pldem(plobj):
	def __init__(self,filename=None, options=ploptions()):
		self.vertices_LatLng = []
		super().__init__()
		self.kindstr = 'dem'
		self.posLists = None	# list of 'posList'(LinearRing) : [*,4,3]
		if filename is not None:
			self.loadFile(filename, options=options)

	def loadFile(self,filename, options=ploptions(), num_search_coincident=100):
		tree, root = super().loadFile(filename)
		nsmap = self.removeNoneKeyFromDic(root.nsmap)
		lt,rb = convertMeshcodeToLatLon( os.path.basename(filename).split('_')[0] )
		#center = (np.array(lt)+np.array(rb))/2
		center = ( lt[0]*0.8+rb[0]*0.2, lt[1]*0.2+rb[1]*0.8 )
		# posLists
		vals = tree.xpath('/core:CityModel/core:cityObjectMember/dem:ReliefFeature/dem:reliefComponent/dem:TINRelief/dem:tin/gml:TriangulatedSurface/gml:trianglePatches/gml:Triangle/gml:exterior/gml:LinearRing/gml:posList', namespaces=nsmap)
		self.posLists = np.array([str2floats(v).reshape((-1,3)) for v in vals])
		if options.bHeightZero:
			self.posLists[:,:,2] = 0
		#print(self.posLists.shape)
		# convert to XYZ
		posLists = copy.deepcopy(self.posLists)
		usebit = []
		for x in posLists:
			for yidx,y in enumerate(x):
				bit = True
				if options.div6toQuarter is not None:
					lat = y[0]
					lon = y[1]
					if lat < center[0]:
						lat = 0
					else:
						lat = 1
					if lon < center[1]:
						lon = 0
					else:
						lon = 1
					if (lat,lon) != options.div6toQuarter:
						bit = False
				if yidx < 3:
					usebit.append(bit)
				y[:] = convertPolarToCartsian(*y)
		# to vertices and triangles
		#   integrate vertices that are coincident.
		mesh = plmesh()
		mesh.triangles = np.zeros( (posLists.shape[0], 3), dtype=np.int )
		for xidx,x in enumerate(posLists):
			for yidx,y in enumerate(x[:3]):
				newid = -1
				if options.div6toQuarter is None:
					num = xidx
					if num > num_search_coincident:
						num = num_search_coincident
					for _id, vvv in enumerate( mesh.vertices[xidx-num:] ):
						if vvv[0]==y[0] and vvv[1]==y[1] and vvv[2]==y[2]:
							newid = _id + xidx - num
							break
				if newid < 0:
					newid = len(mesh.vertices)
					mesh.vertices.append(y)
					self.vertices_LatLng.append(self.posLists[xidx, yidx][:3])
				mesh.triangles[xidx,yidx] = newid
		# remove 
		if options.div6toQuarter is not None:
			newtriangles = []
			for tri in mesh.triangles:
				if usebit[tri[0]] and usebit[tri[1]] and usebit[tri[2]]:
					newtriangles.append( tri )
			mesh.triangles = np.array(newtriangles)
			
		# set texture
		if options.basemap["use"]:
			from plateaupy.basemap import TMSDownloader as tms
			# get basemap image from TileMapService
			startLoc = tms.GeoCoordinate(*np.min(np.array(self.vertices_LatLng).reshape(-1, 3), axis=0)[:2])
			endLoc = tms.GeoCoordinate(*np.max(np.array(self.vertices_LatLng).reshape(-1, 3), axis=0)[:2])
			layer = tms.LayerType.SATELLITE if options.basemap["layer"] == 0 else tms.LayerType.ROADMAP
			zoom = options.basemap["zoom"]
			imgBasemap = tms.generateImage(startLoc, endLoc, zoom=zoom, tms=tms.TMS.GoogleMaps, layer=layer, isCrop=True)

			# seve basemap image
			basemap_file = f"basemap_{os.path.basename(filename).split('_')[0]}.png"
			basemap_path = os.path.join(options.texturedir, "basemap")
			if not os.path.exists(basemap_path):
				os.makedirs(basemap_path)
			basemap_file = os.path.join(basemap_path, basemap_file)
			cv2.imwrite(basemap_file, imgBasemap)

			# set texture file
			mesh.texture_filename = basemap_file

			pList = np.array(self.vertices_LatLng).reshape(-1, 3)
			# min-max normalization
			vmax = np.max(pList, axis=0)
			vmin = np.min(pList, axis=0)
			mm_norm = ((np.array(pList) - vmin) / (vmax-vmin))
			# create uv map
			mesh.triangle_uvs.extend( [ [mm_norm[x][1], 1 - mm_norm[x][0]] for x in mesh.triangles.reshape((-1)) ] )
			mesh.triangle_material_ids.extend([0]*len(mesh.triangles))

		self.meshes.append(mesh)


