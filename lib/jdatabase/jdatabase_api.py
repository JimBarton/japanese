#!/usr/bin/python -tt

import sys
import os
import re
import MySQLdb

from google.appengine.api import app_identity
import cloudstorage as gcs

class Jdatabase:
  _connection_name = os.environ.get('CLOUDSQL_CONNECTION_NAME')
  _user = os.environ.get('CLOUDSQL_USER')
  _password = os.environ.get('CLOUDSQL_PASSWORD')
  _database = os.environ.get('CLOUDSQL_DATABASE')
  _charset = 'utf8'

  def __init__(self):
    if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
      cloudsql_unix_socket = os.path.join('/cloudsql', _connection_name)
      self.conn = MySQLdb.connect(unix_socket=cloudsql_unix_socket, user=self._user, passwd=self._password, db=self._database, charset=self._charset)
    
    else:
      self.conn = MySQLdb.connect(host='127.0.0.1', user=self._user, passwd=self._password, db=self._database, charset=self._charset)
    
    self.cursor = self.conn.cursor()

  def close_connection(self):
    if self.conn:
      self.conn.commit()
      self.conn.close()

  def recreate_tables(self):
    kanji = Jkanji()
    
    sql_command = 'DROP TABLE kanji'
    try:
      self.cursor.execute(sql_command)
    except MySQLdb.Error as e:
      print e
      sys.exit(1)

    sql_command = 'CREATE TABLE IF NOT EXISTS kanji(id VARCHAR(1) PRIMARY KEY,grade VARCHAR(2),strokecount VARCHAR(2),frequency VARCHAR(4),jlpt CHAR(1),known BOOLEAN)'
    try:
      self.cursor.execute(sql_command)
    except MySQLdb.Error as e:
      print e
      sys.exit(1)

    # read the kanjidic file from the cloud storage if running in deployment
    # otherwise read from local file (can't get the stubs to work at the moment)
    if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
      bucket_name = os.environ.get('BUCKET_NAME', app_identity.get_default_gcs_bucket_name())
      bucket = '/' + bucket_name
    else:
      bucket = '.'

    filename = bucket + '/kanjidic2.xml'
    
    # If running in deployment then open file using google cloud library
    # otherwise use local file in this directory. cloud library should work but doesn't at the moment
    #if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
      #with gcs.open(filename) as kanji_file:
    #else:
    with open(filename) as kanji_file:
      # read each line in the kanji file and extract each kanji and its data based on tags
      for line in kanji_file:
        search = re.search(r'<literal>(.+)</literal>',line)
        if search:
          kanji.dict['id'] = search.group(1)
          continue
        search = re.search(r'<grade>(\d+)</grade>', line)
        if search:
          kanji.dict['grade'] = search.group(1)
          continue
        search = re.search(r'<stroke_count>(\d+)</stroke_count>', line)
        if search and not kanji.dict['strokecount']:
          kanji.dict['strokecount'] = search.group(1)
          continue
        search = re.search(r'<freq>(\d+)</freq>', line)
        if search:
          kanji.dict['frequency'] = search.group(1)
          continue
        search = re.search(r'<jlpt>(\d+)</jlpt>', line)
        if search:
          kanji.dict['jlpt'] = search.group(1)
          continue
        search = re.search(r'</character>', line)
        if search:
          # we have reached the end of one kanji tag
          # if this is a jouyou kanji, write out the current kanji to the database
          if (kanji.dict['grade'] >= '1' and kanji.dict['grade'] <= '8'):
            self.insert_kanji(kanji)
          # reset the string variables for the next kanji
          kanji.dict['id'] = ''
          kanji.dict['grade'] = ''
          kanji.dict['strokecount'] = ''
          kanji.dict['frequency'] = ''
          kanji.dict['jlpt'] = ''

  def retrieve_kanji(self, character):
    kanji = Jkanji()
    sql_command = 'SELECT * FROM kanji WHERE id = (%s)'
    try:
      self.cursor.execute(sql_command, (character))
    except MySQLdb.Error as e:
      print e
    else:
      data = self.cursor.fetchone()
      #print self.cursor._last_executed
      #print self.cursor.rowcount
      #print data
      kanji.dict['id'], kanji.dict['grade'], kanji.dict['strokecount'], kanji.dict['frequency'], kanji.dict['jlpt'], kanji.dict['known'] = data
    return kanji

  def insert_kanji(self, kanji):
    sql_command = 'INSERT INTO kanji(id, grade, strokecount, frequency, jlpt, known)VALUES(%s,%s,%s,%s,%s,FALSE)'
    try:
      self.cursor.execute(sql_command, (kanji.dict['id'], kanji.dict['grade'], kanji.dict['strokecount'], kanji.dict['frequency'], kanji.dict['jlpt']))
    except MySQLdb.Error as e:
      print e

class Jkanji:
  def __init__(self):
    self.dict = {'id': '','grade': '',
           'strokecount': '',
           'frequency': '',
           'jlpt': '',
           'known': ''
           }

  def update_kanji(self, new_data):
    for feature, value in new_data.values():
      if value:
        self.kanji_dictionary[feature] = value

