#!/usr/bin/python -tt
#coding=utf-8

import os
import sys
import re
import cgi
import urllib
import logging
logging.basicConfig(level=logging.INFO)

import webapp2
import jinja2

from google.appengine.api import memcache
from google.appengine.api import users
import jdatabase

# set up our jinja environment
templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(templates_dir),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
          
# function to get the current user and store it
def get_user():
  data_dict = {}
  data_dict['user'] = users.get_current_user()
  if data_dict['user']:
    data_dict['nickname'] = data_dict['user'].nickname()
    data_dict['logout_url'] = users.create_logout_url('/')
  else:
    data_dict['login_url'] = users.create_login_url('/')

  return data_dict

# global data dictionary for storing the rendered data
kanji_data = {}
kanji_base_url = r'kanjilookup?character='
admin_data = {}

# open a connection to the database
db = jdatabase.Jdatabase()

class MainPage(webapp2.RequestHandler):
  """ Class for the main page which is overview page """
  template = JINJA_ENVIRONMENT.get_template('index.html')

  def get(self):
    """ Render a the lookup page with no selected kanji, requesting input from user """
    summary_data = {}
    summary_data['user_dict'] = get_user()
    summary_data['status'] = db.retrieve_status()
    self.response.write(self.template.render(summary_data))

class KanjiLookup(webapp2.RequestHandler):
  """ Class for displaying results of kanji lookup. Allows user to perform various operations
      on the displayed data """
  template = JINJA_ENVIRONMENT.get_template('kanji.html')
  
  def get(self):
    """ Ask user to enter kanji """
    kanji_data.clear()
    kanji_data['user_dict'] = get_user()
    kanji_data['base_url'] = kanji_base_url

    if self.request.get('character'):
      kanji_literal = self.request.get('character')
      logging.info(kanji_literal)
    
      kanji_data['kanji_dict'] = db.retrieve_kanji(kanji_literal)
      if 'literal' in kanji_data['kanji_dict']:
        kanji_data['vocab_list'], kanji_data['character_dict'] = db.retrieve_kanji_vocab(kanji_data['kanji_dict']['literal'])

    logging.info(kanji_data)
    self.response.write(self.template.render(kanji_data))

  def post(self):
    """ Retrieve any input from the user and update data accordingly"""
    logging.info(self.request.POST)
    if 'known' in self.request.POST:
      kanji_data['kanji_dict']['known'] = True
      kanji_data['character_dict'][kanji_data['kanji_dict']['literal']] = 1
      db.update_kanji_known_status(kanji_data['kanji_dict'])
    elif 'unknown' in self.request.POST:
      kanji_data['kanji_dict']['known'] = False
      kanji_data['character_dict'][kanji_data['kanji_dict']['literal']] = 0
      db.update_kanji_known_status(kanji_data['kanji_dict'])
    elif 'vocabupdatelist' in self.request.POST:
      list_of_vocab_to_hide = self.request.get_all('unhidden')
      list_of_vocab_to_unhide = self.request.get_all('hidden')
      list_of_vocab_to_know = self.request.get_all('vocabnotknown')
      list_of_vocab_to_unknow = self.request.get_all('vocabknown')
      for elem, vocab in enumerate(kanji_data['vocab_list']):
        if str(vocab['id']) in list_of_vocab_to_hide:
          kanji_data['vocab_list'][elem]['display'] = False
      	  db.update_vocab_display_status(vocab)
        elif str(vocab['id']) in list_of_vocab_to_unhide:
          kanji_data['vocab_list'][elem]['display'] = True
      	  db.update_vocab_display_status(vocab)
        if str(vocab['id']) in list_of_vocab_to_know:
          kanji_data['vocab_list'][elem]['known'] = True
      	  db.update_vocab_known_status(vocab)
        elif str(vocab['id']) in list_of_vocab_to_unknow:
          kanji_data['vocab_list'][elem]['known'] = False
      	  db.update_vocab_known_status(vocab)
    
    logging.info(kanji_data)

    # render the current kanji
    self.response.write(self.template.render(kanji_data))

class KanjiList(webapp2.RequestHandler):
  """ Display all jouyou kanji on summary page """
  template = JINJA_ENVIRONMENT.get_template('kanjilist.html')
  
  def get(self):
    current_data = { 'display_order' : 'grade',
  	                 'min_stroke' : 1, 'max_stroke' : 29, 'min_freq' : 1, 'max_freq' : 2501,
                     'no_freq' : False,
                     'min_grade' : 1, 'max_grade' : 8, 'min_jlpt' : 1, 'max_jlpt' : 4,
                     'no_jlpt' : False, 'known_flag' : 'true'
                   }
    current_data['user_dict'] = get_user()
    current_data['base_url'] = kanji_base_url
    current_data['kanji_list'] = {}

    """ Read all kanji and display them """
    logging.info(self.request.query_string)
    if self.request.get("displayOrder"):
      current_data['display_order'] = self.request.get("displayOrder")
    if self.request.get("strokeMinInput"):
      current_data['min_stroke'] = self.request.get("strokeMinInput")
    if self.request.get("strokeMaxInput"):
      current_data['max_stroke'] = self.request.get("strokeMaxInput")
    if self.request.get("freqMinInput"):
      current_data['min_freq'] = self.request.get("freqMinInput")
    if self.request.get("freqMaxInput"):
      current_data['max_freq'] = self.request.get("freqMaxInput")
    if self.request.get("noFreq"):
      current_data['no_freq'] = True
    if self.request.get("gradeMinInput"):
      current_data['min_grade'] = self.request.get("gradeMinInput")
    if self.request.get("gradeMaxInput"):
      current_data['max_grade'] = self.request.get("gradeMaxInput")
    if self.request.get("jlptMinInput"):
      current_data['min_jlpt'] = self.request.get("jlptMinInput")
    if self.request.get("jlptMaxInput"):
      current_data['max_jlpt'] = self.request.get("jlptMaxInput")
    if self.request.get("noJlpt"):
      current_data['no_jlpt'] = True
    if self.request.get("knownFlag"):
      current_data['known_flag'] = self.request.get("knownFlag")
      
    logging.info(current_data)
    current_data['kanji_list'] = db.retrieve_many_kanji(current_data)
    logging.info(current_data['kanji_list'])
     
    self.response.write(self.template.render(current_data))

class Administration(webapp2.RequestHandler):
  """ Class for displaying database stats and option to recreate the database from scratch.
      Just for development really
  """
  template = JINJA_ENVIRONMENT.get_template('admin.html')

  def get(self):
    admin_data['user_dict'] = get_user()
    """ Retrieve the latest database stats and display them """
    admin_data['status'] = db.retrieve_status()
    self.response.write(self.template.render(admin_data))

  def post(self):
    """ Recreate the entire database and re-display stats """
    db.recreate_base_data()
    admin_data['status'] = db.retrieve_status()
 
    admin_data['flag'] = True
    self.response.write(self.template.render(admin_data))
        
app = webapp2.WSGIApplication([
    (r'/', MainPage),
    (r'/kanjilookup', KanjiLookup),
    (r'/kanjilist', KanjiList),
    (r'/admin', Administration)
], debug=True)
