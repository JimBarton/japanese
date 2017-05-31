#!/usr/bin/python -tt

import sys
import os
import MySQLdb

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

  def create_tables(self):
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
    sql_command = 'INSERT INTO kanji(id, grade, strokecount, frequency, jlpt, known)VALUES(%s,%s,%s,%s,%s,%d)'
    try:
      self.cursor.execute(sql_command, (kanji.dict['id'], kanji.dict['grade'], kanji.dict['strokecount'], kanji.dict['frequency'], kanji.dict['jlpt'], kanji.dict['known']))
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

