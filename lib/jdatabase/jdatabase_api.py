#!/usr/bin/python -tt
#coding=utf-8

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
    # set up the database connection
    if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
      cloudsql_unix_socket = os.path.join('/cloudsql', _connection_name)
      self.conn = MySQLdb.connect(unix_socket=cloudsql_unix_socket, user=self._user, passwd=self._password, db=self._database, charset=self._charset)
    
    else:
      self.conn = MySQLdb.connect(host='127.0.0.1', user=self._user, passwd=self._password, db=self._database, charset=self._charset)
    
    self.cursor = self.conn.cursor()

    # setup bucket name. read from cloud storage if running in deployment
    # otherwise read from local file (can't get the stubs to work at the moment)
    if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
      self.bucket_name = os.environ.get('BUCKET_NAME', app_identity.get_default_gcs_bucket_name())
      self.bucket = '/' + bucket_name
      self.open_function = gcs.open
    else:
      self.bucket = '.'
      self.open_function = open
      
    self.kanji_xmlfile = self.bucket + '/kanjidic2.xml'
    self.vocab_xmlfile = self.bucket + '/JMdict_e.xml'
    self.grammar_textfile = self.bucket + '/grammar.txt'

  def close_connection(self):
    if self.conn:
      self.conn.commit()
      self.conn.close()

  def recreate_base_data(self):
    self.recreate_tables()
    self.read_kanji_file()
    self.read_vocabulary_file()
    self.read_grammar_file()
  
  def recreate_tables(self):
    sql_command_list = []
    sql_command_list.append('DROP TABLE IF EXISTS kanji, vocabulary, grammar')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS kanji(kanji_id VARCHAR(1) PRIMARY KEY,grade VARCHAR(2),strokecount VARCHAR(2),frequency VARCHAR(4),jlpt CHAR(1),kanji_known BOOLEAN)')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS vocabulary(vocab_id VARCHAR(255) PRIMARY KEY,reading VARCHAR(255),vocab_known BOOLEAN)')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS grammar(grammar_id VARCHAR(255) PRIMARY KEY,description VARCHAR(255))')
    for sql_command in sql_command_list:
      print sql_command
      try:
        self.cursor.execute(sql_command)
      except MySQLdb.Error as e:
        print e
      
  def read_kanji_file(self):
    kanji = Jkanji()
 
    # read the kanjidic file
    with self.open_function(self.kanji_xmlfile) as kanji_file:
      # read each line in the kanji file and extract each kanji and its data based on tags
      for line in kanji_file:
        search = re.search(r'<literal>(.+)</literal>',line)
        if search:
          kanji.dict['kanji_id'] = search.group(1)
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
          kanji.dict['kanji_id'] = ''
          kanji.dict['grade'] = ''
          kanji.dict['strokecount'] = ''
          kanji.dict['frequency'] = ''
          kanji.dict['jlpt'] = ''

  def read_vocabulary_file(self):
    vocab = Jvocab()
    entry_list = []
    senses_list = []
    count = 0
    # read the vocab file
    with self.open_function(self.vocab_xmlfile) as vocab_file:
      # read each line in the vocab file and extract each vocab and its data based on tags
      for line in vocab_file:
        if "<entry>" in line:
          # start of a new vocab entry to process it
          for line in vocab_file:
            entry_list.append(line)
            if "</entry>" in line:
              # end of this vocabulary element so extract required information
              entry_string = "".join(entry_list)
              if "<re_pri>" in entry_string:
                search = re.search(r'<keb>(.+)</keb>',entry_string)
                if search:
                  vocab.dict['vocab_id'] = search.group(1)
                search = re.search(r'<reb>(.+)</reb>',entry_string)
                if search:
                  vocab.dict['reading'] = search.group(1)
                  if vocab.dict['vocab_id'] == '':
                    vocab.dict['vocab_id'] = search.group(1)
                senses = re.findall(r'<sense>(.+)</sense>',entry_string, re.DOTALL)
                for sense in senses:
                  pos = re.search(r'<pos>(.+)</pos>',sense)
                  glosses = re.findall(r'<gloss>(.+)</gloss>',sense)
                  senses_list.append((pos.group(1),glosses))
                vocab.dict['meanings'] = senses_list
                self.insert_vocab(vocab)
                status = str(count) + '...'
                #if count%1000:
                 #caller.response.write(status)
                count += 1
              entry_list = []
              vocab.dict['vocab_id'] = ''
              vocab.dict['reading'] = ''
              vocab.dict['meanings'][:] = []
              break
          #search stored text for <r_ele>
          #if found
            #extract required info from stored text and write to database
          #clear the stored text
          #break from this inner for loop
  
  def read_grammar_file(self):
    with self.open_function(self.grammar_textfile) as grammar_file:
      content = grammar_file.read()
      grammar_tuples = re.findall(r'(\S+)\s+(.+)',content)
      for id,description in grammar_tuples:
        self.insert_grammar(id,description)
  
  def retrieve_kanji(self, character):
    kanji = Jkanji()
    vocab_list = []
    vocabulary = Jvocab()
    sql_command = 'SELECT * FROM kanji WHERE kanji_id = (%s)'
    try:
      self.cursor.execute(sql_command, (character))
    except MySQLdb.Error as e:
      print e
    else:
      data = self.cursor.fetchone()
      #print self.cursor._last_executed
      #print self.cursor.rowcount
      #print data
      kanji.dict['kanji_id'], kanji.dict['grade'], kanji.dict['strokecount'], kanji.dict['frequency'], kanji.dict['jlpt'], kanji.dict['kanji_known'] = data
    
    sql_command = 'SELECT vocab_id FROM vocabulary WHERE vocab_id LIKE (%s)'
    try:
      self.cursor.execute(sql_command, ("%" + character + "%"))
    except MySQLdb.Error as e:
      print e
    else:
      kanji.dict['vocab_list'] = self.cursor.fetchall()
    return kanji

  def retrieve_status(self):
    status = {}
    tables = ('kanji', 'vocabulary', 'grammar')
    for table in tables:
      sql_command = 'SELECT * FROM ' + table
      self.cursor.execute(sql_command)
      status[table] = self.cursor.rowcount
    return status

  def insert_kanji(self, kanji):
    sql_command = 'INSERT INTO kanji(kanji_id, grade, strokecount, frequency, jlpt, kanji_known)VALUES(%s,%s,%s,%s,%s,FALSE)'
    try:
      self.cursor.execute(sql_command, (kanji.dict['kanji_id'], kanji.dict['grade'], kanji.dict['strokecount'], kanji.dict['frequency'], kanji.dict['jlpt']))
    except MySQLdb.Error as e:
      print e

  def insert_vocab(self, vocab):
    sql_command = 'INSERT INTO vocabulary(vocab_id, reading, vocab_known)VALUES(%s,%s,FALSE)'
    try:
      self.cursor.execute(sql_command, (vocab.dict['vocab_id'], vocab.dict['reading']))
    except MySQLdb.Error as e:
      print e

  def insert_grammar(self, type,description):
    sql_command = 'INSERT INTO grammar(grammar_id, description)VALUES(%s,%s)'
    try:
      self.cursor.execute(sql_command, (type, description))
    except MySQLdb.Error as e:
      print e
      if re.search(r'Duplicate',e.args[1]):
        new_type = type + '2'
        sql_command = 'INSERT INTO grammar(grammar_id, description)VALUES(%s,%s)'
        try:
          self.cursor.execute(sql_command, (new_type, description))
        except MySQLdb.Error as e:
          print e
        else:
          print 'Duplicate resolved as', new_type

class Jkanji:
  def __init__(self):
    self.dict = {'kanji_id': '','grade': '',
           'strokecount': '',
           'frequency': '',
           'jlpt': '',
           'kanji_known': '',
           'vocab_list':[]
           }

  def update_kanji(self, new_data):
    for feature, value in new_data.values():
      if value:
        self.kanji_dictionary[feature] = value

class Jvocab:
  def __init__(self):
    self.dict = {'vocab_id': '','reading': '',
           'meanings':[],
           'vocab_known':''}

class Jgrammar:
  def __init__(self):
    self.dict = {'grammar_id': '','description': ''}
