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
    """ Set up the database connection. We use the environment variables from above whih are picked up
        by appenginefrom the app.yaml file. We need to check whether we are in production or not and configure
        connection accordingly.
        We also set up the file bucket to use. This should work in development using stub functions but doesn't
        seem to so currently picking up from local directory.
        After finding the correct bucket we set names for the 3 files we need to parse
    """
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

  def __del__(self):
    if self.conn:
      self.conn.commit()
      self.conn.close()

  def recreate_base_data(self):
    """ This function recreates all the database tables by re-parsing the files and populating the tables
    """
    self.recreate_tables()
    self.parse_kanji_file()
    self.parse_grammar_file()
    self.parse_vocabulary_file()
    #self.create_kanjivocab()
  
  def recreate_tables(self):
    """ This function deletes any previous tables from the database and recreates them """
    sql_command_list = []
    sql_command_list.append('DROP TABLE IF EXISTS KanjiVocabulary, Kanji, Vocabulary, Grammar')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS Kanji('\
      'id SMALLINT PRIMARY KEY AUTO_INCREMENT,'\
      'literal VARCHAR(1),'\
      'grade VARCHAR(2),'\
      'strokecount VARCHAR(2),'\
      'frequency VARCHAR(4),'\
      'jlpt CHAR(1),'\
      'known BOOLEAN)')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS Vocabulary('\
      'id MEDIUMINT PRIMARY KEY AUTO_INCREMENT,'\
      'literal VARCHAR(255),'\
      'reading VARCHAR(255),'\
      'known BOOLEAN)')
    sql_command_list.append('CREATE TABLE IF NOT EXISTS Grammar('\
      'id SMALLINT PRIMARY KEY AUTO_INCREMENT,'\
      'name VARCHAR(255),'\
      'description VARCHAR(255))')
    #sql_command_list.append('CREATE TABLE IF NOT EXISTS KanjiVocabulary('\
      #'kanjiid SMALLINT NOT NULL,'\
      #'vocabularyid MEDIUMINT NOT NULL,'\
      #'PRIMARY KEY (kanjiid, vocabularyid),'\
      #'FOREIGN KEY (kanjiid) REFERENCES Kanji (id),'\
      #'FOREIGN KEY (vocabularyid) REFERENCES Vocabulary (id))')

    for sql_command in sql_command_list:
      print sql_command
      try:
        self.cursor.execute(sql_command)
      except MySQLdb.Error as e:
        print e
      else:
        self.conn.commit()
      
  def parse_kanji_file(self):
    """ Parse the kanji XML file. There is one <literal> tag for each kanji. We read line by line
        and search for particular tags then pick up what is inside the tag. When we reach the end
        of a <literal> tag then we know that we have finished reading one character and store the
        read data to the database
        """
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
          kanji['literal'] = ''
          kanji['grade'] = ''
          kanji['strokecount'] = ''
          kanji['frequency'] = ''
          kanji['jlpt'] = ''

  def parse_vocabulary_file(self):
    """ Parse the vocabulary XML file. Each entry is wrapped in an <entry> tag. We read line by line
        until we find the start of this tag and then start storing the following lines until we reach
        the end of the tag. We have then stored an entire entry and can parse it, picking out the
        appropriate info and writing to the database
    """
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

                # insert the retreived vocabulary entry into the database
                self.insert_vocab(vocab)

              # clear the local vocab entry ready for the next one
              entry_list = []
              vocab['literal'] = ''
              vocab['reading'] = ''
              vocab['meanings'] = []
              vocab['char_list'] = []
              break
  
  def create_kanjivocab(self):
    """ This creates a mapping table for kanji character to vocabulary. One character can appear in
        many vocab and one vocab can contain many kani. However this table is not actually used at
        the moment - I just created it as part of studying mapping tables. As the kanji are embedded
        in each vocab anyway I don't think the table is actually needed
    """
    # get all the kanji from the Kanji table
    sql_command = 'SELECT * FROM Kanji'
    try:
      self.cursor.execute(sql_command)
    except MySQLdb.Error as e:
      print e
    else:
      kanji_tuple = self.cursor.fetchall()
      # select all vocabulary entries where each kanji appears
      sql_command1 = 'SELECT * FROM Vocabulary WHERE literal LIKE (%s)'
      for kanji in kanji_tuple:
        try:
          self.cursor.execute(sql_command1, ("%" + kanji[1] + "%"))
        except MySQLdb.Error as e:
          print e
        else:
          vocab_tuple = self.cursor.fetchall()
          # insert a row in the table for each vocab entry that corresponds to this kanji
          sql_command2 = 'INSERT INTO KanjiVocabulary '\
            'VALUES(%s,%s)'
          for vocab in vocab_tuple:
            try:
              self.cursor.execute(sql_command2, (kanji[0],vocab[0]))
            except MySQLdb.Error as e:
              print e
            else:
              self.conn.commit()
  
  def parse_grammar_file(self):
    """ Parse the grammar text file. This is a list of 2 whitespace separated columns.
        The first column is the grammar type and the second is a description. We read
        the entire file and then unpack the tuple into field which is then written to
        the database
    """
    with self.open_function(self.grammar_textfile) as grammar_file:
      content = grammar_file.read()
      grammar_tuples = re.findall(r'(\S+)\s+(.+)',content)
      for id,description in grammar_tuples:
        self.insert_grammar(id,description)
  
  def retrieve_kanji(self, character):
    """ Retrieve a kanji entry from the database, passing the character itself as input.
        We return a dictionary of the unpacked tuple
    """
    kanji_dict = {}
    sql_command = 'SELECT * FROM Kanji WHERE literal = (%s)'
    try:
      self.cursor.execute(sql_command, (character))
    except MySQLdb.Error as e:
      print e
    else:
      data = self.cursor.fetchone()
      if data:
        print data
        kanji_dict['id'], kanji_dict['literal'], kanji_dict['grade'] ,kanji_dict['strokecount'], kanji_dict['frequency'], kanji_dict['jlpt'], kanji_dict['known'] = data
      else:
        print "Kanji does not exist in the database"
    
    return kanji_dict

  def retrieve_kanji_vocab(self, character):
    """ Retrieves all vocabulary containing a given kanji character, passed as argument.
        We return a list of the vocab lists with each vocab list having the following form:
        (tuple of the vocab entry in the database)[list of kanji in the vocab][list of known flags for the kanji]
        E.g. (5949, u'\u6d77\u85fb', u'\u304b\u3044\u305d\u3046', 0), [u'\u6d77', u'\u85fb'], [1, 0]
             (vocab id, vocab literal, vocab in kana, vocabulary known flag), [list of kanji in vocab], [known flags for the kanji]]
    """
    vocab_display_list = []

    # retrieve the vocab for this kanji
    sql_command = 'SELECT * FROM Vocabulary WHERE literal LIKE (%s)'   
    try:
      self.cursor.execute(sql_command, ("%" + character + "%"))
    except MySQLdb.Error as e:
      print e
    else:
      vocab_tuple = self.cursor.fetchall()
      # for each returned vocab, retrieve all its kanji one by one and create a list of the kanji and
      # corresponding list of known flags. If the kanji is not in the database (it is not a jouyou kanji)
      # then we can set the known flag to 'unknown'
      # NB: this needs improving to not retrieve kanji that have already appeared before which is especially
      # true for the target kanji as this obviously appears in all the vocab and doesn't need to be retrieved
      # multiple times
      for elem, vocab in enumerate(vocab_tuple):
        char_list = []
        known_list = []
        for character in vocab[1]:
          kanji = self.retrieve_kanji(character)
          if kanji:
            char_list.append(character)
            known_list.append(kanji['known'])
          else:
            char_list.append(character)
            known_list.append(0)
        # append the vocab tuple, kanji list and known list to complex vocab list
        vocab_display_list.append([vocab,char_list,known_list])

    # return the complex list
    return vocab_display_list

  def retrieve_status(self):
    """ Retrieves the number of entries in each table and returns this as as dictionary """
    status = {}
    #tables = ('Kanji', 'Vocabulary', 'Grammar', 'KanjiVocabulary')
    tables = ('Kanji', 'Vocabulary', 'Grammar')
    for table in tables:
      sql_command = 'SELECT * FROM ' + table
      self.cursor.execute(sql_command)
      status[table] = self.cursor.rowcount
    return status

  def insert_kanji(self, kanji):
    """ Inserts a new kanji into the database using a kanji dictionary as input. Always marked as
        unknown in the first instance
    """
    sql_command = 'INSERT INTO Kanji(literal, grade, strokecount, frequency, jlpt, known)VALUES(%s,%s,%s,%s,%s,FALSE)'
    try:
      self.cursor.execute(sql_command, (kanji['literal'], kanji['grade'], kanji['strokecount'], kanji['frequency'], kanji['jlpt']))
    except MySQLdb.Error as e:
      print e
    else:
      self.conn.commit()

  def insert_vocab(self, vocab):
    """ Inserts a new vocabulary entry into the database using a vocab dictionary as input
    """
    sql_command = 'INSERT INTO Vocabulary(literal, reading, known)VALUES(%s,%s,FALSE)'
    try:
      self.cursor.execute(sql_command, (vocab['literal'], vocab['reading']))
    except MySQLdb.Error as e:
      print e
    else:
      self.conn.commit()

  def insert_grammar(self,name,description):
    """ Inserts a new grammar entry into the database using a pair of args for type and description """
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
          self.conn.commit()

  def update_known_status(self, kanji):
    """ Update the 'known' status of a kanji using a kanji dictionary as input """
    sql_command = 'UPDATE Kanji SET known=(%s) WHERE id=(%s)'
    try:
      self.cursor.execute(sql_command, (kanji['known'], kanji['id']))
    except MySQLdb.Error as e:
      print e
    else:
      self.conn.commit()
