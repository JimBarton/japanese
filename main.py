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
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
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
current_data = {}
current_data['base_url'] = r'kanjilookup?character='

# open a connection to the guest database
db = jdatabase.Jdatabase()

class MainPage(webapp2.RequestHandler):
  """ Class for the main page which is overview page """
  template = JINJA_ENVIRONMENT.get_template('index.html')

  def get(self):
    """ Render a the lookup page with no selected kanji, requesting input from user """
    current_data['user_dict'] = get_user()
    self.response.write(self.template.render(current_data))

  def post(self):
    """ Retrieve the kanji character input by the user and redirect to the lookup
        page for this kanji
    """
    kanji_literal = cgi.escape(self.request.get('lookup'))
    self.redirect('kanjilookup?%s' % urllib.urlencode({'character': kanji_literal.encode('utf-8')}))

class KanjiLookup(webapp2.RequestHandler):
  """ Class for displaying results of kanji lookup. Allows user to perform various operations
      on the displayed data """
  template = JINJA_ENVIRONMENT.get_template('kanji.html')
  current_data['user_dict'] = get_user()
  
  def get(self):
    """ Ask user to enter kanji """
    print "a get"
    current_data['kanji_dict'] = {}
    current_data['vocab_list'] = []
    current_data['character_dict'] = {}

    if self.request.get('character'):
      kanji_literal = self.request.get('character')
      logging.info(kanji_literal)
    
      current_data['kanji_dict'] = db.retrieve_kanji(kanji_literal)
      current_data['vocab_list'], current_data['character_dict'] = db.retrieve_kanji_vocab(current_data['kanji_dict']['literal'])

    self.response.write(self.template.render(current_data))

  def post(self):
    logging.info(self.request.POST)
    logging.info(self.request.GET)
    
    """ Retrieve any input from the user and update data accordingly"""
    logging.info(current_data)
    
    # If this is a new kanji lookup then retrieve it from the database and add it to memory cache
    logging.info(self.request.POST)
    if 'lookup' in self.request.POST:
      print "lookup"
      kanji_literal = cgi.escape(self.request.get('lookup'))
      current_data['kanji_dict'] = db.retrieve_kanji(kanji_literal)
      current_data['vocab_list'], current_data['character_dict'] = db.retrieve_kanji_vocab(current_data['kanji_dict']['literal'])
      print "redirect"
      #self.redirect('kanjilookup?%s' % urllib.urlencode({'character': kanji_literal.encode('utf-8')}), abort=True)
      return self.redirect('kanjilookup?%s' % urllib.urlencode({'character': kanji_literal.encode('utf-8')}), abort=True)
      print "redirected"
    elif 'known' in self.request.POST:
      current_data['kanji_dict']['known'] = True
      current_data['character_dict'][current_data['kanji_dict']['literal']] = 1
      db.update_kanji_known_status(current_data['kanji_dict'])
    elif 'unknown' in self.request.POST:
      current_data['kanji_dict']['known'] = False
      current_data['character_dict'][current_data['kanji_dict']['literal']] = 0
      db.update_kanji_known_status(current_data['kanji_dict'])
    elif 'vocabupdatelist' in self.request.POST:
      list_of_vocab_to_hide = self.request.get_all('unhidden')
      list_of_vocab_to_unhide = self.request.get_all('hidden')
      list_of_vocab_to_know = self.request.get_all('vocabnotknown')
      list_of_vocab_to_unknow = self.request.get_all('vocabknown')
      for elem, vocab in enumerate(current_data['vocab_list']):
        if str(vocab['id']) in list_of_vocab_to_hide:
          current_data['vocab_list'][elem]['display'] = False
      	  db.update_vocab_display_status(vocab)
        elif str(vocab['id']) in list_of_vocab_to_unhide:
          current_data['vocab_list'][elem]['display'] = True
      	  db.update_vocab_display_status(vocab)
        if str(vocab['id']) in list_of_vocab_to_know:
          current_data['vocab_list'][elem]['known'] = True
      	  db.update_vocab_known_status(vocab)
        elif str(vocab['id']) in list_of_vocab_to_unknow:
          current_data['vocab_list'][elem]['known'] = False
      	  db.update_vocab_known_status(vocab)
    
    logging.info(current_data)

    # render the current kanji
    self.response.write(self.template.render(current_data))

class KanjiList(webapp2.RequestHandler):
  """ Display all jouyou kanji on summary page """
  template = JINJA_ENVIRONMENT.get_template('summary.html')
  current_data['display_order'] = None
  current_data['user_dict'] = get_user()
  
  def get(self):
    """ Read all kanji and display them """
    logging.info(self.request.query_string)
    if self.request.get("displayOrder"):
      current_data['display_order'] = self.request.get("displayOrder")
      current_data['min_stroke'] = self.request.get("strokeMinInput")
      current_data['max_stroke'] = self.request.get("strokeMaxInput")
      current_data['min_freq'] = self.request.get("freqMinInput")
      current_data['max_freq'] = self.request.get("freqMaxInput")
      if self.request.get("noFreq"):
        current_data['no_freq'] = True
      else:
        current_data['no_freq'] = False
      current_data['min_grade'] = self.request.get("gradeMinInput")
      current_data['max_grade'] = self.request.get("gradeMaxInput")
      current_data['min_jlpt'] = self.request.get("jlptMinInput")
      current_data['max_jlpt'] = self.request.get("jlptMaxInput")
      if self.request.get("noJlpt"):
        current_data['no_jlpt'] = True
      else:
        current_data['no_jlpt'] = False
      current_data['known_flag'] = self.request.get("knownFlag")
      
      current_data['kanji_list'] = db.retrieve_many_kanji(current_data)
      logging.info(current_data['kanji_list'])
     
    self.response.write(self.template.render(current_data))

  def post(self):
    """ Read user inputs and display kanji accordingly """
    logging.info(self.request.POST)    
    self.response.write(self.template.render(current_data))

class RecreateData(webapp2.RequestHandler):
  """ Class for displaying database stats and option to recreate the database from scratch.
      Just for development really
  """
  template = JINJA_ENVIRONMENT.get_template('recreatedata.html')
  current_data['user_dict'] = get_user()

  def get(self):
    """ Retrieve the latest database stats and display them """
    current_data['status'] = db.retrieve_status()
    self.response.write(self.template.render(current_data))

  def post(self):
    """ Recreate the entire database and re-display stats """
    db.recreate_base_data()
    current_data['status'] = db.retrieve_status()
 
    current_data['flag'] = True
    self.response.write(self.template.render(current_data))
        
app = webapp2.WSGIApplication([
    (r'/', MainPage),
    (r'/kanjilookup', KanjiLookup),
    (r'/kanjilist', KanjiList),
    (r'/recreatedata', RecreateData)
], debug=True)
