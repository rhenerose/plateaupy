from numpy.lib.polynomial import poly
from numpy.lib.twodim_base import tri
from plateaupy.plobj import plmesh, plobj
from plateaupy.plutils import *
from plateaupy.ploptions import ploptions
from plateaupy.thirdparty.earcutpython.earcut.earcut import earcut
import numpy as np
import copy
import pickle
import sys
import os
import cv2
from lxml import etree
import lxml
from tqdm import tqdm

_floorheight = 2	# fixed value, the height of 1 floor in meter.

class Building:
	def __init__(self):
		self.id = None	# gml:id
		self.attr = dict()
		self.usage = None
		self.measuredHeight = None
		self.storeysAboveGround = None
		self.storeysBelowGround = None
		self.address = None
		self.buildingDetails = dict()
		self.extendedAttribute = dict()

		self.lod0RoofEdge = []
		self.lod1Solid = []

		#self.lod2Solid = []
		# lod2MultiSurface
		self.lod2ground = dict()
		self.lod2roof = dict()
		self.lod2wall = dict()
		# self.partex = appParameterizedTexture()
	def __str__(self):
		return 'Building id={}\n\
usage={}, measuredHeight={}, storeysAboveGround={}, storeysBelowGround={}\n\
address={}\n\
buildingDetails={}\n\
extendedAttribute={}\n\
attr={}'\
		.format(self.id, self.usage, self.measuredHeight, self.storeysAboveGround, self.storeysBelowGround, \
			self.address, self.buildingDetails, self.extendedAttribute, self.attr)
	# get vertices, triangles from lod0RoofEdge
	def getLOD0polygons(self, height=None):
		vertices = None
		triangles = None
		if len(self.lod0RoofEdge) > 0:
			vertices = []
			for x in self.lod0RoofEdge[0]:
				xx = copy.deepcopy(x)
				if height is not None:
					xx[2] = height
				vertices.append( convertPolarToCartsian( *xx ) )
			vertices = np.array(vertices)
			res = earcut(np.array(vertices,dtype=np.int).flatten(), dim=3)
			if len(res) > 0:
				triangles = np.array(res).reshape((-1,3))
		return vertices, triangles

class appParameterizedTexture:
	def __init__(self):
		self.imageURI = None
		self.cachePath = None
		self.targets = dict()
	@classmethod
	def search_list(cls, applist, polyid):
		for app in applist:
			if polyid in app.targets.keys():
				return app
		return None

class plbldg(plobj):
	class Surface():
		def __init__(self, polygon, paramTexture):
			self.polygon = polygon
			self.paramTexture = paramTexture

	def __init__(self,filename=None, options=ploptions()):
		super().__init__()
		self.kindstr = 'bldg'
		self.buildings = []	# list of Building
		self.options = options
		if filename is not None:
			self.loadFile(filename, options=options)
		self.partex = []

	def createBuilding(self, bld, nsmap):
		options = self.options
		b = Building()

		# gml:id
		b.id = bld.attrib['{'+nsmap['gml']+'}id']
		# stringAttribute
		stringAttributes = bld.xpath('.//gen:stringAttribute', namespaces=nsmap)
		for at in stringAttributes:
			b.attr[at.attrib['name']] = at.getchildren()[0].text
		# genericAttributeSet
		genericAttributeSets = bld.xpath('.//gen:genericAttributeSet', namespaces=nsmap)
		for at in genericAttributeSets:
			vals = dict()
			for ch in at.getchildren():
				vals[ ch.attrib['name'] ] = ch.getchildren()[0].text
			b.attr[at.attrib['name']] = vals
		# usage
		for at in bld.xpath('.//bldg:usage', namespaces=nsmap):
			b.usage = at.text
		# measuredHeight
		for at in bld.xpath('.//bldg:measuredHeight', namespaces=nsmap):
			b.measuredHeight = at.text
		# storeysAboveGround
		for at in bld.xpath('.//bldg:storeysAboveGround', namespaces=nsmap):
			b.storeysAboveGround = at.text
		# storeysBelowGround
		for at in bld.xpath('.//bldg:storeysBelowGround', namespaces=nsmap):
			b.storeysBelowGround = at.text
		# address
		try:	# there are 2 names: 'xAL' and 'xal'..
			for at in bld.xpath('.//bldg:address/core:Address/core:xalAddress/xAL:AddressDetails/xAL:Address', namespaces=nsmap):
				b.address = at.text
		except lxml.etree.XPathEvalError as e:
			for at in bld.xpath('.//bldg:address/core:Address/core:xalAddress/xal:AddressDetails/xal:Address', namespaces=nsmap):
				b.address = at.text
		# buildingDetails
		for at in bld.xpath('.//uro:buildingDetails/uro:BuildingDetails', namespaces=nsmap):
			for ch in at.getchildren():
				tag = ch.tag
				tag = tag[ tag.rfind('}')+1: ]
				b.buildingDetails[tag] = ch.text
		# extendedAttribute
		for at in bld.xpath('.//uro:extendedAttribute/uro:KeyValuePair', namespaces=nsmap):
			ch = at.getchildren()
			b.extendedAttribute[ch[0].text] = ch[1].text
		# lod0RoofEdge
		vals = bld.xpath('.//bldg:lod0RoofEdge/gml:MultiSurface/gml:surfaceMember/gml:Polygon/gml:exterior/gml:LinearRing/gml:posList', namespaces=nsmap)
		b.lod0RoofEdge = [str2floats(v).reshape((-1,3)) for v in vals]
		# lod1Solid
		vals = bld.xpath('.//bldg:lod1Solid/gml:Solid/gml:exterior/gml:CompositeSurface/gml:surfaceMember/gml:Polygon/gml:exterior/gml:LinearRing/gml:posList', namespaces=nsmap)
		b.lod1Solid = [str2floats(v).reshape((-1,3)) for v in vals]
		minheight = 0
		if options.bHeightZero:
			# calc min height
			minheight = 10000
			for x in b.lod1Solid:
				if minheight > np.min(x[:,2]):
					minheight = np.min(x[:,2])
			if b.storeysBelowGround is not None:
				minheight = minheight + (int(b.storeysBelowGround) * _floorheight)
			if minheight == 10000:
				minheight = 0
			for x in b.lod1Solid:
				x[:,2] -= minheight
		# lod2Solid
		#  nothing to do for parsing <bldg:lod2Solid>
		# lod2MultiSurface : Ground, Roof, Wall
		for bb in bld.xpath('.//bldg:boundedBy/bldg:GroundSurface/bldg:lod2MultiSurface/gml:MultiSurface/gml:surfaceMember/gml:Polygon', namespaces=nsmap):
			polyid = '#' + bb.attrib['{'+nsmap['gml']+'}id']
			vals = bb.xpath('.//gml:exterior/gml:LinearRing/gml:posList', namespaces=nsmap)
			surf = [str2floats(v).reshape((-1,3)) for v in vals]
			if options.bHeightZero:
				if minheight == 0:
					# calc min height
					minheight = 10000
					for x in surf:
						if minheight > np.min(x[:,2]):
							minheight = np.min(x[:,2])
					if b.storeysBelowGround is not None:
						minheight = minheight + (int(b.storeysBelowGround) * _floorheight)
					if minheight == 10000:
						minheight = 0
				for x in surf:
					x[:,2] -= minheight
			# b.lod2ground[polyid] = surf
			app = appParameterizedTexture.search_list( self.partex, polyid )
			b.lod2ground[polyid] = self.Surface(surf, app)

		for bb in bld.xpath('.//bldg:boundedBy/bldg:RoofSurface/bldg:lod2MultiSurface/gml:MultiSurface/gml:surfaceMember/gml:Polygon', namespaces=nsmap):
			polyid = '#' + bb.attrib['{'+nsmap['gml']+'}id']
			vals = bb.xpath('.//gml:exterior/gml:LinearRing/gml:posList', namespaces=nsmap)
			surf = [str2floats(v).reshape((-1,3)) for v in vals]
			if options.bHeightZero:
				for x in surf:
					x[:,2] -= minheight
			# b.lod2roof[polyid] = surf
			app = appParameterizedTexture.search_list( self.partex, polyid )
			b.lod2roof[polyid] = self.Surface(surf, app)

		for bb in bld.xpath('.//bldg:boundedBy/bldg:WallSurface/bldg:lod2MultiSurface/gml:MultiSurface/gml:surfaceMember/gml:Polygon', namespaces=nsmap):
			polyid = '#' + bb.attrib['{'+nsmap['gml']+'}id']
			vals = bb.xpath('.//gml:exterior/gml:LinearRing/gml:posList', namespaces=nsmap)
			surf = [str2floats(v).reshape((-1,3)) for v in vals]
			if options.bHeightZero:
				for x in surf:
					x[:,2] -= minheight
			# b.lod2wall[polyid] = surf
			app = appParameterizedTexture.search_list( self.partex, polyid )
			b.lod2wall[polyid] = self.Surface(surf, app)

		# bldPart = bld.xpath("bldg:consistsOfBuildingPart", namespaces=nsmap)
		# for bPart in bldPart:
		# 	b = self.createBuilding(bPart, self.partex, nsmap)

		return b

	def getTextureCachePath(self, filePath):
		return os.path.join(self.options.texturedir, os.path.basename(filePath) + '.png')

	def getTextureCache(self, imageURI):
		# convert .tif into .png, because o3d.io.read_image() fails.
		imagePath = os.path.join(os.path.dirname(self.filename), imageURI)
		img = cv2.imread(imagePath)
		if img is not None:
			cachePath = self.getTextureCachePath(imageURI)
			try:
				if cv2.imwrite(cachePath, img):
					return cachePath
			except Exception as e:
				return None

		return None

	def loadFile(self,filename, options=ploptions()):
		tree, root = super().loadFile(filename)
		nsmap = self.removeNoneKeyFromDic(root.nsmap)

		# scan appearanceMember
		self.partex = []
		print("Load Textures ...")
		paramTextures = tree.xpath('/core:CityModel/app:appearanceMember/app:Appearance/app:surfaceDataMember/app:ParameterizedTexture', namespaces=nsmap)
		for app in tqdm(paramTextures):
			par = appParameterizedTexture()
			for at in app.xpath('app:imageURI', namespaces=nsmap):
				par.imageURI = at.text
				if options.bUseLOD2texture:
					par.cachePath = self.getTextureCache(par.imageURI)

			for at in app.xpath('app:target', namespaces=nsmap):
				uri = at.attrib['uri']
				colist = [str2floats(v).reshape((-1,2)) for v in at.xpath('app:TexCoordList/app:textureCoordinates', namespaces=nsmap)]
				maxnum = max(map(lambda x:x.shape[0],colist))
				for cidx,co in enumerate(colist):
					last = co[-1].reshape(-1,2)
					num = maxnum - co.shape[0]
					if num > 0:
						colist[cidx] = np.append(co,np.tile(co[-1].reshape(-1,2),(num,1)),axis=0)
				par.targets[uri] = np.array(colist)

			self.partex.append(par)

		# scan cityObjectMember
		blds = tree.xpath('/core:CityModel/core:cityObjectMember/bldg:Building', namespaces=nsmap)
		print("Load Buildings ...")
		for bld in tqdm(blds):
			b = self.createBuilding(bld, nsmap)
			self.buildings.append(b)

		def getMesh(mList, texture_file):
			for m in mList:
				if texture_file is None:
					if m.texture_filename is None:
						return m
				else:
					if m.texture_filename == texture_file:
						return m

			# no mesh
			newMesh = plmesh()
			newMesh.texture_filename = texture_file
			mList.append(newMesh)
			return newMesh

		# vertices, triangles
		# if (not options.bUseLOD2texture) or options.bUseLOD0:
		# 	mesh = plmesh()
		for b in self.buildings:
			# if options.bUseLOD2texture and (not options.bUseLOD0):
			# 	mesh = plmesh()
			
			meshList = []
			if options.bUseLOD0:
				# LOD0
				mesh = getMesh(meshList, None)
				vertices, triangles = b.getLOD0polygons()
				if vertices is not None and triangles is not None:
					vstart = len(mesh.vertices)
					mesh.vertices.extend( vertices )
					mesh.triangles.extend( triangles + vstart )
			elif b.lod2ground or b.lod2roof or b.lod2wall:
				# LOD2

				# ground
				for key, value in b.lod2ground.items():
					mesh = getMesh(meshList, value.paramTexture.cachePath if value.paramTexture is not None else None)
					vertices = [ convertPolarToCartsian( *x ) for x in value.polygon[0] ]
					res = earcut(np.array(vertices,dtype=np.int).flatten(), dim=3)
					if len(res) > 0:
						vstart = len(mesh.vertices)
						mesh.vertices.extend( vertices )
						triangles = np.array(res).reshape((-1,3))
						mesh.triangles.extend( triangles + vstart )
						# texture
						if options.bUseLOD2texture:
							# mesh.texture_filename = value.paramTexture.cachePath
							if value.paramTexture is not None and key in value.paramTexture.targets.keys():
								mesh.triangle_uvs.extend( [ value.paramTexture.targets[key][0,x] for x in triangles.reshape((-1)) ] )
								mesh.triangle_material_ids.extend( [0]*len(triangles) )
							else:	# add dummy uvs, material_ids    (The texture can not appear if the numbers of triangles are different between triangles and them.)
								mesh.triangle_uvs.extend( [ np.zeros((2)) for x in range(len(triangles)*3) ] )
								mesh.triangle_material_ids.extend( [0]*len(triangles) )
				# roof
				for key, value in b.lod2roof.items():
					mesh = getMesh(meshList, value.paramTexture.cachePath if value.paramTexture is not None else None)
					vertices = [ convertPolarToCartsian( *x ) for x in value.polygon[0] ]
					res = earcut(np.array(vertices,dtype=np.int).flatten(), dim=3)
					if len(res) > 0:
						vstart = len(mesh.vertices)
						mesh.vertices.extend( vertices )
						triangles = np.array(res).reshape((-1,3))
						mesh.triangles.extend( triangles + vstart )
						# texture
						if options.bUseLOD2texture:
							# mesh.texture_filename = value.paramTexture.cachePath
							if value.paramTexture is not None and key in value.paramTexture.targets.keys():
								mesh.triangle_uvs.extend( [ value.paramTexture.targets[key][0,x] for x in triangles.reshape((-1)) ] )
							else:
								# no key (add dummy uv)
								mesh.triangle_uvs.extend( np.zeros([triangles.size, 2]) )
							mesh.triangle_material_ids.extend( [0]*len(triangles) )
				# wall
				for key, value in b.lod2wall.items():
					mesh = getMesh(meshList, value.paramTexture.cachePath if value.paramTexture is not None else None)
					vertices = [ convertPolarToCartsian( *x ) for x in value.polygon[0] ]
					res = earcut(np.array(vertices,dtype=np.int).flatten(), dim=3)
					if len(res) > 0:
						vstart = len(mesh.vertices)
						mesh.vertices.extend( vertices )
						triangles = np.array(res).reshape((-1,3))
						mesh.triangles.extend( triangles + vstart )
						# texture
						if options.bUseLOD2texture:
							if value.paramTexture is not None and key in value.paramTexture.targets.keys():
								mesh.triangle_uvs.extend( [ value.paramTexture.targets[key][0,x] for x in triangles.reshape((-1)) ] )
							else:
								# no key (add dummy uv)
								mesh.triangle_uvs.extend( np.zeros([triangles.size, 2]) )
							mesh.triangle_material_ids.extend( [0]*len(triangles) )
			else:
				# LOD1
				mesh = getMesh(meshList, None)
				for plist in b.lod1Solid:
					vertices = [ convertPolarToCartsian( *x ) for x in plist ]
					res = earcut(np.array(vertices,dtype=np.int).flatten(), dim=3)
					if len(res) > 0:
						vstart = len(mesh.vertices)
						mesh.vertices.extend( vertices )
						triangles = np.array(res).reshape((-1,3))
						mesh.triangles.extend( triangles + vstart )
						# texture
						if options.bUseLOD2texture:	# add dummy uvs, material_ids    (The texture can not appear if the numbers of triangles are different between triangles and them.)
							mesh.triangle_uvs.extend( [ np.zeros((2)) for x in range(len(triangles)*3) ] )
							mesh.triangle_material_ids.extend( [0]*len(triangles) )
			if options.bUseLOD2texture:
				self.meshes.extend(meshList)
		if not options.bUseLOD2texture:
			self.meshes.extend(meshList)

		for mesh in self.meshes:
			if len(mesh.triangle_uvs):
				# flip uvs y
				mesh.triangle_uvs = (np.array([0, 1]) - mesh.triangle_uvs) * np.array([-1, 1])


