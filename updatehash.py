#!/usr/bin/env python
# -*- coding: utf-8 -*-
import hashlib
import os
import sqlite3
import time
import sys
import stat

def checksumFile(path):
	md5 = hashlib.md5()
	sha1 = hashlib.sha1()
	with open(path,'rb') as f: 
		while True:
			chunk = f.read(2*md5.block_size*sha1.block_size)
			if not chunk:
				return {'md5':md5.hexdigest(), 'sha1':sha1.hexdigest()}
			md5.update(chunk)
			sha1.update(chunk)

def fileInfo(path):
	st = os.lstat(path)
	if not stat.S_ISREG(st.st_mode):
		return None
	return {'mtime':st.st_mtime, 'size':st.st_size}

def initdb(cursor):
	cursor.execute("create table if not exists files(tag,timestamp,path primary key,md5,sha1,mtime,size)")
	cursor.execute("create index if not exists i_files_tag on files(tag)")
	cursor.execute("create index if not exists i_files_path_md5_sha1 on files(path,md5,sha1)")
	cursor.execute("create table if not exists removedfiles(rmtimestamp,tag,timestamp,path,md5,sha1,mtime,size)")

def cacheFileInfo(cursor, path):
	cursor.execute('select mtime,size from files where path = ?', (path,))
	data = cursor.fetchone()
	return data and {'mtime':data[0], 'size':data[1]}

def update(connection,cursor,path):
	cursor.execute("create temp table newfiles(path)")
	cursor.execute("create index i_newfiles_path on newfiles(path)")
	timestamp = time.time()
	currentTime = time.clock()
	lastTime = currentTime
	for d in os.walk(path):
		dirpath=d[0]
		for f in d[2]:
			fpath = os.path.join(dirpath, f)
			if os.path.isfile(fpath):
				fi = fileInfo(fpath)
				if fi is None:
					print "!skipping", fpath
					continue
				cfi = cacheFileInfo(cursor,fpath)
				cursor.execute("insert into newfiles(path) values(?)", (fpath,))
				if fi != cfi:
					print " updating", fpath
					sums = checksumFile(fpath)
					values = ('no tag',timestamp,fpath,sums['md5'],sums['sha1'],fi['mtime'],fi['size'])
					cursor.execute("insert or replace into files(tag,timestamp,path,md5,sha1,mtime,size) values(?,?,?,?,?,?,?)", values)
					
					currentTime = time.clock()
					if abs(lastTime-currentTime) >= 10:
						lastTime = currentTime
						connection.commit()
						print "commit!"
	connection.commit()
	print "commit!"
	print "cleaning up..."
	cursor.execute("create temp table deletedfiles(path)")
	cursor.execute("create index i_deletedfiles_path on deletedfiles(path)")
	likepath=('' + path).replace('%', '%%') + '%';
	cursor.execute("insert into deletedfiles(path) select path from files where path like ?", (likepath,));
	cursor.execute("delete from deletedfiles where path in newfiles");
	cursor.execute("insert into removedfiles(rmtimestamp,tag,timestamp,path,md5,sha1,mtime,size) select ?,tag,timestamp,path,md5,sha1,mtime,size from files where path in deletedfiles", (timestamp,))
	cursor.execute("delete from files where path in deletedfiles")
	connection.commit()

def walk(db,path):
	connection = sqlite3.connect(db)
	connection.text_factory = str # For utf-8 file names…
	cursor = connection.cursor()
	initdb(cursor)
	update(connection, cursor, path)
	cursor.close()

def help():
	print 'Usage : %s database-file directory' % sys.argv[0]
	sys.exit(1)

if len(sys.argv) != 3:
	help()
for arg in sys.argv[1:]:
	if arg == '-h' or arg == '--help':
		help()

walk(sys.argv[1], sys.argv[2])
