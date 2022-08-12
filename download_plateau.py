import urllib.request, os, sys, shutil, glob
from distutils.dir_util import copy_tree
import argparse

# from pyunpack import Archive
from zipfile import ZipFile
import py7zr

from gml_dataset import datasets

dbnames = [db['name'] for db in datasets]

parser = argparse.ArgumentParser(description='Download & extract PLATEAU dataset')
parser.add_argument('db',type=str,help='-1(all) or specify dataset, as str or index in '+str(dbnames))
parser.add_argument('--basedir',type=str,default='CityGML2020',help='dst base directory')
parser.add_argument('--no_download',action='store_true',help='not download files.')
parser.add_argument('--no_extract',action='store_true',help='not extract files.')

args = parser.parse_args()

dbs = []
if args.db=='-1':
	dbs = datasets
elif args.db in dbnames:
	dbs = [datasets[ dbnames.index(args.db) ]]
elif args.db.isdecimal() and 0 <= int(args.db) and int(args.db) < len(datasets):
	dbs = [datasets[int(args.db)]]
else:
	print('No dataset:',args.db)
	sys.exit(-1)

def download(url,dstpath):
	os.makedirs(dstpath,exist_ok=True)
	filename = os.path.basename(url)
	print('  download',url,'to',dstpath)
	urllib.request.urlretrieve(url,dstpath+'/'+filename)

def extract_zip(srcPath,dstPath):
	with ZipFile(srcPath, 'r') as archive:
		archive.extractall(dstPath)

def extract_7z(srcPath,dstPath):
	with py7zr.SevenZipFile(srcPath, mode='r') as archive:
		archive.extractall(path=dstPath)

def extract(url,dstpath):
	os.makedirs(dstpath,exist_ok=True)
	fname = os.path.splitext(os.path.basename(url))
	if fname[1] == '.zip':
		print('  extract_zip {} to {}'.format(url,dstpath))
		extract_zip(url,dstpath)
		return True
	elif fname[1] == '.7z':
		print('  extract_7z {} to {}'.format(url,dstpath))
		extract_7z(url,dstpath)
		return True
	elif fname[1] == '.png' or fname[1] == '.xml' or fname[1] == '.xlsx' or fname[1] == '.xls':
		print('  copy file {} to {}'.format(url,dstpath))
		shutil.copy(url,dstpath)
		return True
	else:
		print('unknown ext',fname[1])
		return False

def copy_files(url,dstpath):
	cmd='cp -a {} {}'.format(url,dstpath)
	copy_tree_(url,dstpath)
def copy_tree_(url,dstpath):
	copy_tree(url,dstpath)
	print('  copy_tree {} {}'.format(url,dstpath))

def move_tree(url,dstpath):
	# listup source files
	files = os.listdir(url)

	# check dstpath exists
	if not os.path.exists(dstpath):
		# make dstpath directory
		os.makedirs(dstpath)

	# move files or directories
	for filePath in files:
		toPath = os.path.join(dstpath, filePath)
		# check dstpath
		if os.path.exists(toPath):
			# remove dstpath
			if os.path.isdir(toPath):
				shutil.rmtree(toPath)
			if os.path.isfile(toPath):
				os.remove(toPath)
		# move file or directory
		shutil.move(os.path.join(url, filePath), toPath)
	print('  move_tree {} {}'.format(url,dstpath))

basedir = args.basedir
ardir = 'archive'
for db in dbs:
	print(db['name'])
	_basedir = basedir+'/'+db['name']
	_ardir = _basedir+'/'+ardir+'/'
	_codelistdir = _basedir+'/codelists/'
	_metadatadir = _basedir+'/metadata/'
	_specdir = _basedir+'/specification/'
	_udxdir = _basedir+'/udx/'
	_alldir = _basedir
	_tmpdir = _basedir+'/.tmp'

	if not args.no_download:
		if 'specs' in db:
			for xx in db['specs']:
				download(xx,_ardir)
		if 'codelists' in db:
			for xx in db['codelists']:
				download(xx,_ardir)
		if 'metadata' in db:
			for xx in db['metadata']:
				download(xx,_ardir)
		if 'citygml' in db:
			for xx in db['citygml']:
				download(db['citygml_base']+xx,_ardir)
		if 'citygml_all' in db:
			for xx in db['citygml_all']:
				download(xx,_ardir)
	if not args.no_extract:
		if 'specs' in db:
			for xx in db['specs']:
				extract(_ardir+os.path.basename(xx),_specdir)
		if 'codelists' in db:
			for xx in db['codelists']:
				extract(_ardir+os.path.basename(xx),_codelistdir)
		if 'metadata' in db:
			for xx in db['metadata']:
				extract(_ardir+os.path.basename(xx),_metadatadir)
		if 'citygml' in db:
			for xx in db['citygml']:
				if os.path.exists(_tmpdir):
					shutil.rmtree(_tmpdir)
				extract(_ardir+os.path.basename(xx),_tmpdir)
				for yy in glob.glob(_tmpdir+'/*'):
					pname = os.path.splitext(os.path.basename(yy))[0]
					extract(yy,_udxdir+pname)
			shutil.rmtree(_tmpdir)
		if 'citygml_all' in db:
			for xx in db['citygml_all']:
				if os.path.exists(_tmpdir):
					shutil.rmtree(_tmpdir)
				extract(_ardir+os.path.basename(xx),_tmpdir)
				tmpfiles = glob.glob(_tmpdir+'/*')
				if 'udx' in tmpfiles:
					move_tree( _tmpdir, _alldir )
				elif len(tmpfiles)>0 and os.path.exists(tmpfiles[0]+'/udx'):
					move_tree( tmpfiles[0], _alldir )
				else:
					bFound = False
					for yy in tmpfiles:
						if os.path.splitext(yy)[1] == '.zip' or os.path.splitext(yy)[1] == '.7z':
							extract(yy, _tmpdir)
					for tt in ['codelists','metadata','specification','udx']:
						for zz in glob.glob(_tmpdir+'/**/'+tt,recursive=True):
							move_tree(zz,_alldir+'/'+tt)
							bFound = True
					if not bFound:
						for tt in ['bldg','tran','luse','urf','dem','fld','tnm','lsld','brid','frn']:
							for zz in glob.glob(_tmpdir+'/**/'+tt,recursive=True):
								move_tree(zz,_udxdir+'/'+tt)
								bFound = True
					if not bFound:
						print('\nerror! unknown dir structure:', tmpfiles)
				for yy in glob.glob(_udxdir+'**/*.zip',recursive=True):
					extract(yy, os.path.dirname(yy))
				for yy in glob.glob(_udxdir+'**/*.7z',recursive=True):
					extract(yy, os.path.dirname(yy))
			shutil.rmtree(_tmpdir)
