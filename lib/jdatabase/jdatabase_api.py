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
    #self.recreate_tables()
    #self.parse_kanji_file()
    #self.parse_grammar_file()
    #self.parse_vocabulary_file()
    self.create_kanjivocab()
  
  def recreate_tables(self):
    sql_command_list = []
    sql_command_list.append('DROP TABLE IF EXISTS KanjiVocabulary, Kanji, Vocabulary, Grammar')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS Kanji('\
      'id SMALLINT PRIMARY KEY AUTO_INCREMENT,'\
      'literal VARCHAR(1),'\
      'grade VARCHAR(2),'\
      'strokecount VARCHAR(2),'\
      'frequency VARCHAR(4),'\
      'jlpt CHAR(1),'\
      'known BOOLEAN,'\
      'style VARCHAR(255))')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS Vocabulary('\
      'id MEDIUMINT PRIMARY KEY AUTO_INCREMENT,'\
      'literal VARCHAR(255),'\
      'reading VARCHAR(255),'\
      'known BOOLEAN)')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS Grammar('\
      'id SMALLINT PRIMARY KEY AUTO_INCREMENT,'\
      'name VARCHAR(255),'\
      'description VARCHAR(255))')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS KanjiVocabulary('\
      'kanjiid SMALLINT NOT NULL,'\
      'vocabularyid MEDIUMINT NOT NULL,'\
      'PRIMARY KEY (kanjiid, vocabularyid),'\
      'FOREIGN KEY (kanjiid) REFERENCES Kanji (id),'\
      'FOREIGN KEY (vocabularyid) REFERENCES Vocabulary (id))')

    for sql_command in sql_command_list:
      print sql_command
      try:
        self.cursor.execute(sql_command)
      except MySQLdb.Error as e:
        print e
      
  def parse_kanji_file(self):
    kanji = {'literal':'',   
             'grade': '',
             'strokecount': '',
             'frequency': '',
             'jlpt': ''}
 
    # read the kanjidic file
    with self.open_function(self.kanji_xmlfile) as kanji_file:
      # read each line in the kanji file and extract each kanji and its data based on tags
      for line in kanji_file:
        search = re.search(r'<literal>(.+)</literal>',line)
        if search:
          kanji['literal'] = search.group(1)
          continue
        search = re.search(r'<grade>(\d+)</grade>', line)
        if search:
          kanji['grade'] = search.group(1)
          continue
        search = re.search(r'<stroke_count>(\d+)</stroke_count>', line)
        if search:
          kanji['strokecount'] = search.group(1)
          continue
        search = re.search(r'<freq>(\d+)</freq>', line)
        if search:
          kanji['frequency'] = search.group(1)
          continue
        search = re.search(r'<jlpt>(\d+)</jlpt>', line)
        if search:
          kanji['jlpt'] = search.group(1)
          continue
        search = re.search(r'</character>', line)
        if search:
          # we have reached the end of one kanji tag
          # if this is a jouyou kanji, write out the current kanji to the database
          if ('grade' in kanji and kanji['grade'] >= '1' and kanji['grade'] <= '8'):
            self.insert_kanji(kanji)
          # reset the string variables for the next kanji
          #kanji.clear()
          kanji['literal'] = ''
          kanji['grade'] = ''
          kanji['strokecount'] = ''
          kanji['frequency'] = ''
          kanji['jlpt'] = ''

  def parse_vocabulary_file(self):
    vocab = {'literal': '',
             'reading': '',
             'meanings':''}
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
                  vocab['literal'] = search.group(1)
                # reb tag stores the reading of the vocab in hiragana (pronunciation)
                # if there's a reb tag and no keb tag then just store the reading as the vocab
                # this probably means the vocab doesn't contain any kanji
                search = re.search(r'<reb>(.+)</reb>',entry_string)
                if search:
                  vocab['reading'] = search.group(1)
                  if vocab['literal'] == '':
                    vocab['literal'] = search.group(1)
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
                vocab['meanings'] = senses_list
                
                # we also break down and store each vocabulary entry into its list of characters
                # for example 辞書 will also be stored as 辞、書. 聞く as 聞、く
                #vocab_char_list = re.findall(r'(.)',vocab['vocab_id'].decode('utf8'))
                #print vocab_char_list
                #vocab['char_list'] = ''.join(vocab_char_list)

                # insert the retreived vocabulary entry into the database
                self.insert_vocab(vocab)

              # clear the local vocab entry ready for the next one
              entry_list = []
              #vocab.clear()
              vocab['literal'] = ''
              vocab['reading'] = ''
              vocab['meanings'] = []
              #vocab['char_list'] = []
              break
  
  def create_kanjivocab(self):
    sql_command = 'SELECT * FROM Kanji'
    try:
      self.cursor.execute(sql_command)
    except MySQLdb.Error as e:
      print e
    else:
      kanji_tuple = self.cursor.fetchall()
      #print "kanji_tuple"
      #print kanji_tuple
      sql_command1 = 'SELECT * FROM Vocabulary WHERE literal LIKE (%s)'
      for kanji in kanji_tuple:
        try:
          #print repr(kanji[1])
          self.cursor.execute(sql_command1, ("%" + kanji[1] + "%"))
        except MySQLdb.Error as e:
          print e
        else:
          vocab_tuple = self.cursor.fetchall()
          #print "vocab_tuple"
          #print vocab_tuple
          sql_command2 = 'INSERT INTO KanjiVocabulary '\
            'VALUES(%s,%s)'
          for vocab in vocab_tuple:
            try:
              #print "inserting"
              #print kanji[0], vocab[0]
              self.cursor.execute(sql_command2, (kanji[0],vocab[0]))
            except MySQLdb.Error as e:
              print e
            #else:
              #print "inserted"
          #sys.exit(1)
      
  def parse_grammar_file(self):
    with self.open_function(self.grammar_textfile) as grammar_file:
      content = grammar_file.read()
      grammar_tuples = re.findall(r'(\S+)\s+(.+)',content)
      for id,description in grammar_tuples:
        self.insert_grammar(id,description)
  
  def retrieve_kanji(self, character):
    kanji_dict = {}
    sql_command = 'SELECT * FROM Kanji WHERE literal = (%s)'
    try:
      self.cursor.execute(sql_command, (character))
    except MySQLdb.Error as e:
      print e
    else:
      data = self.cursor.fetchone()
      if data:
        #print data
        kanji_dict['id'], kanji_dict['literal'], kanji_dict['grade'] ,kanji_dict['strokecount'], kanji_dict['frequency'], kanji_dict['jlpt'], kanji_dict['kanji_known'], kanji_dict['style'] = data
      else:
        print "Kanji does not exist in the database"
    
    return kanji_dict

  def retrieve_kanji_with_vocab(self, character):
    kanji = self.retrieve_kanji(character)
    sql_command = 'SELECT * FROM KanjiVocabulary WHERE literal LIKE (%s)'
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
    tables = ('Kanji', 'Vocabulary', 'Grammar', 'KanjiVocabulary')
    for table in tables:
      sql_command = 'SELECT * FROM ' + table
      self.cursor.execute(sql_command)
      status[table] = self.cursor.rowcount
    return status

  def insert_kanji(self, kanji):
    sql_command = 'INSERT INTO Kanji(literal, grade, strokecount, frequency, jlpt, known, style)VALUES(%s,%s,%s,%s,%s,FALSE,%s)'
    try:
      self.cursor.execute(sql_command, (kanji['literal'], kanji['grade'], kanji['strokecount'], kanji['frequency'], kanji['jlpt'], kanji['literal']))
    except MySQLdb.Error as e:
      print e

  def set_kanji_known_flag(self, character, flag):
    sql_command = "UPDATE Kanji SET known = (%s) WHERE literal = (%s)";
    try:
      self.cursor.execute(sql_command, (flag, character))
    except MySQLdb.Error as e:
      print e

  def insert_vocab(self, vocab):
    sql_command = 'INSERT INTO Vocabulary(literal, reading, known)VALUES(%s,%s,FALSE)'
    try:
      self.cursor.execute(sql_command, (vocab['literal'], vocab['reading']))
    except MySQLdb.Error as e:
      print e

  def insert_grammar(self,name,description):
    sql_command = 'INSERT INTO Grammar(name, description)VALUES(%s,%s)'
    try:
      self.cursor.execute(sql_command, (name, description))
    except MySQLdb.Error as e:
      print e
      if re.search(r'Duplicate',e.args[1]):
        new_name = name + '2'
        sql_command = 'INSERT INTO Grammar(name, description)VALUES(%s,%s)'
        try:
          self.cursor.execute(sql_command, (new_name, description))
        except MySQLdb.Error as e:
          print e
        else:
          print 'Duplicate resolved as', new_name
