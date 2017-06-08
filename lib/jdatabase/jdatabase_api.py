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
    self.parse_kanji_file()
    self.parse_grammar_file()
    self.parse_vocabulary_file()
  
  def recreate_tables(self):
    sql_command_list = []
    sql_command_list.append('DROP TABLE IF EXISTS kanji, vocabulary, grammar')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS kanji(kanji_id VARCHAR(1) PRIMARY KEY,grade VARCHAR(2),strokecount VARCHAR(2),frequency VARCHAR(4),jlpt CHAR(1),kanji_known BOOLEAN)')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS vocabulary(vocab_id VARCHAR(255) PRIMARY KEY,reading VARCHAR(255),char_list VARCHAR(255),vocab_known BOOLEAN)')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS grammar(grammar_id VARCHAR(255) PRIMARY KEY,description VARCHAR(255))')
    for sql_command in sql_command_list:
      print sql_command
      try:
        self.cursor.execute(sql_command)
      except MySQLdb.Error as e:
        print e
      
  def parse_kanji_file(self):
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

  def parse_vocabulary_file(self):
    vocab = Jvocab()
    entry_list = []
    senses_list = []
    vocab_char_list = []
    # read the vocab file
    with self.open_function(self.vocab_xmlfile) as vocab_file:
      # read each line in the vocab file and extract each vocab and its data based on tags
      for line in vocab_file:
        # entry tag us start of a new vocab entry. Store lines until get to end of entry
        if "<entry>" in line:
          for line in vocab_file:
            entry_list.append(line)
            # if end of this vocabulary element, extract required information
            if "</entry>" in line:
              entry_string = "".join(entry_list)
              # we are only interested in storing entries marked as "common"
              common_entry = re.search("news1|ichi1|spec1|spec2|gai1", entry_string)
              if common_entry:
                # search for the keb tab which stores the literal vocab (primary key)
                search = re.search(r'<keb>(.+)</keb>',entry_string)
                if search:
                  vocab.dict['vocab_id'] = search.group(1)
                # reb tag stores the reading of the vocab in hiragana (pronunciation)
                # if there's a reb tag and no keb tag then just store the reading as the vocab
                # this probably means the vocab doesn't contain any kanji
                search = re.search(r'<reb>(.+)</reb>',entry_string)
                if search:
                  vocab.dict['reading'] = search.group(1)
                  if vocab.dict['vocab_id'] == '':
                    vocab.dict['vocab_id'] = search.group(1)
                # there is one sense tag for each English meaning of the vocab
                # loop over each and extract the grammar marker (pos) and English words (gloss)
                # store the extracted data as the meanings
                # THIS IS TBD!!!
                senses = re.findall(r'<sense>(.+)</sense>',entry_string, re.DOTALL)
                for sense in senses:
                  pos = re.search(r'<pos>(.+)</pos>',sense)
                  #print pos.group(1) + " -latest pos"
                  glosses = re.findall(r'<gloss>(.+)</gloss>',sense)
                  senses_list.append((pos.group(1),glosses))
                vocab.dict['meanings'] = senses_list
                
                # we also break down and store each vocabulary entry into its list of characters
                # for example 辞書 will also be stored as 辞、書. 聞く as 聞、く
                vocab_char_list = re.findall(r'(.)',vocab.dict['vocab_id'].decode('utf8'))
                #print vocab_char_list
                #char_list = list(vocab.dict['vocab_id'])
                #print char_list
                #for each_char in vocab.dict['vocab_id'].decode('utf8'):
                  #vocab_char_list.append(each_char)
                  #print repr(each_char)
                vocab.dict['char_list'] = ''.join(vocab_char_list)
                #vocab.dict['char_list'] = ','.join(vocab.dict['vocab_id'])
                #vocab.dict['char_list'] = vocab.dict['vocab_id'].decode('utf8')

                # insert the retreived vocabulary entry into the database
                #print vocab.dict
                #print repr(vocab.dict['char_list'])
                #sys.exit(1)
                self.insert_vocab(vocab)
                #sys.exit(1)
              # clear the local vocab entry ready for the next one
              entry_list = []
              vocab.dict['vocab_id'] = ''
              vocab.dict['reading'] = ''
              vocab.dict['meanings'][:] = []
              vocab.dict['char_list'] = []
              break
  
  def parse_grammar_file(self):
    with self.open_function(self.grammar_textfile) as grammar_file:
      content = grammar_file.read()
      grammar_tuples = re.findall(r'(\S+)\s+(.+)',content)
      for id,description in grammar_tuples:
        self.insert_grammar(id,description)
  
  def retrieve_kanji(self, character):
    kanji_dict = {}
    sql_command = 'SELECT * FROM kanji WHERE kanji_id = (%s)'
    try:
      self.cursor.execute(sql_command, (character))
    except MySQLdb.Error as e:
      print e
    else:
      data = self.cursor.fetchone()
      if data:
        #print data
        kanji_dict['kanji_id'], kanji_dict['grade'] ,kanji_dict['strokecount'], kanji_dict['frequency'], kanji_dict['jlpt'], kanji_dict['kanji_known'] = data
      else:
        print "Kanji does not exist in the database"
    
    return kanji_dict

  def retrieve_kanji_with_vocab(self, character):
    kanji = self.retrieve_kanji(character)
    vocabulary = Jvocab()
    sql_command = 'SELECT * FROM vocabulary WHERE vocab_id LIKE (%s)'
    try:
      self.cursor.execute(sql_command, ("%" + character + "%"))
    except MySQLdb.Error as e:
      print e
    else:
      vocab_tuple = self.cursor.fetchall()
      kanji['vocab_list'] = [list(elem) for elem in vocab_tuple]
    #print kanji
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

  def set_kanji_known_flag(self, character, flag):
    sql_command = "UPDATE kanji SET kanji_known = (%s) WHERE kanji_id = (%s)";
    try:
      self.cursor.execute(sql_command, (flag, character))
    except MySQLdb.Error as e:
      print e

  def insert_vocab(self, vocab):
    sql_command = 'INSERT INTO vocabulary(vocab_id, reading, char_list, vocab_known)VALUES(%s,%s,%s,FALSE)'
    try:
      self.cursor.execute(sql_command, (vocab.dict['vocab_id'], vocab.dict['reading'], vocab.dict['char_list']))
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
           'char_list': '',
           'vocab_known': ''
           }

class Jgrammar:
  def __init__(self):
    self.dict = {'grammar_id': '','description': ''}
