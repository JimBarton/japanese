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
import jdatabase

# set up our jinja environment
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
          
# open a connection to the database
db = jdatabase.Jdatabase()

class MainPage(webapp2.RequestHandler):
  """ Class for the main page which is actually currently the kanji lookup page with no
      currently selected kanji
  """
  template = JINJA_ENVIRONMENT.get_template('index.html')
  print "recreation main"

  def get(self):
    """ Render a the lookup page with no selected kanji, requesting input from user """
    self.response.write(self.template.render())

  def post(self):
    """ Retrieve the kanji character input by the user and redirect to the lookup
        page for this kanji
    """
    kanji_literal = cgi.escape(self.request.get('lookup'))
    self.redirect('kanji?%s' % urllib.urlencode({'character': kanji_literal.encode('utf-8')}))

class KanjiLookup(webapp2.RequestHandler):
  """ Class for displaying results of kanji lookup. Allows user to perform various operations
      on the displayed data """
  template = JINJA_ENVIRONMENT.get_template('kanji.html')
  current_data = {}
  current_data['base_url'] = r'kanji?character='
  print "recreation kanjilookup"
  
  def get(self):
    """ Get the current kanji and render it """
    kanji_literal = self.request.get('character')
    logging.info(kanji_literal)
    
    self.current_data['kanji_dict'] = db.retrieve_kanji(kanji_literal)
    self.current_data['vocab_list'], self.current_data['character_dict'] = db.retrieve_kanji_vocab(self.current_data['kanji_dict']['literal'])
    logging.info(self.current_data)

    self.response.write(self.template.render(self.current_data))

  def post(self):
    kanji_literal = self.request.get('character')
    logging.info(kanji_literal)
    
    self.current_data['kanji_dict'] = db.retrieve_kanji(kanji_literal)
    self.current_data['vocab_list'], self.current_data['character_dict'] = db.retrieve_kanji_vocab(self.current_data['kanji_dict']['literal'])

    """ Retrieve any input from the user and update data accordingly"""
    logging.info(self.current_data)
    
    # If this is a new kanji lookup then retrieve it from the database and add it to memory cache
    logging.info(self.request.POST)
    if 'lookup' in self.request.POST:
      kanji_literal = cgi.escape(self.request.get('lookup'))
      self.redirect('kanji?%s' % urllib.urlencode({'character': kanji_literal.encode('utf-8')}))
    elif 'known' in self.request.POST:
      self.current_data['kanji_dict']['known'] = True
      self.current_data['character_dict'][self.current_data['kanji_dict']['literal']] = 1
      db.update_kanji_known_status(self.current_data['kanji_dict'])
    elif 'unknown' in self.request.POST:
      self.current_data['kanji_dict']['known'] = False
      self.current_data['character_dict'][self.current_data['kanji_dict']['literal']] = 0
      db.update_kanji_known_status(self.current_data['kanji_dict'])
    elif 'vocabupdatelist' in self.request.POST:
      list_of_vocab_to_hide = self.request.get_all('unhidden')
      list_of_vocab_to_unhide = self.request.get_all('hidden')
      list_of_vocab_to_know = self.request.get_all('vocabnotknown')
      list_of_vocab_to_unknow = self.request.get_all('vocabknown')
      for elem, vocab in enumerate(self.current_data['vocab_list']):
        if str(vocab['id']) in list_of_vocab_to_hide:
          self.current_data['vocab_list'][elem]['display'] = False
      	  db.update_vocab_display_status(vocab)
        elif str(vocab['id']) in list_of_vocab_to_unhide:
          self.current_data['vocab_list'][elem]['display'] = True
      	  db.update_vocab_display_status(vocab)
        if str(vocab['id']) in list_of_vocab_to_know:
          self.current_data['vocab_list'][elem]['known'] = True
      	  db.update_vocab_known_status(vocab)
        elif str(vocab['id']) in list_of_vocab_to_unknow:
          self.current_data['vocab_list'][elem]['known'] = False
      	  db.update_vocab_known_status(vocab)
    
    logging.info(self.current_data)

    # render the current kanji
    self.response.write(self.template.render(self.current_data))

class KanjiSummary(webapp2.RequestHandler):
  """ Display all jouyou kanji on summary page """
  template = JINJA_ENVIRONMENT.get_template('summary.html')
  current_data = {}
  current_data['base_url'] = r'kanji?character='
  current_data['display_order'] = None
  
  def get(self):
    """ Read all kanji and display them """
    self.current_data['kanji_list'] = db.retrieve_all_kanji()
    self.response.write(self.template.render(self.current_data))

  def post(self):
    """ Read user inputs and display kanji accordingly """
    logging.info(self.request.POST)
    self.current_data['display_order'] = cgi.escape(self.request.get('displayby'))
    self.current_data['kanji_list'] = db.retrieve_all_kanji()
    
    self.response.write(self.template.render(self.current_data))


class RecreateData(webapp2.RequestHandler):
  """ Class for displaying database stats and option to recreate the database from scratch.
      Just for development really
  """
  template = JINJA_ENVIRONMENT.get_template('recreatedata.html')

  def get(self):
    """ Retrieve the latest database stats and display them """
    template_values = db.retrieve_status()
    self.response.write(self.template.render(template_values))

  def post(self):
    """ Recreate the entire database and re-display stats """
    db.recreate_base_data()
    template_values = db.retrieve_status()
 
    template_values['flag'] = True
    #print template_values
    template = JINJA_ENVIRONMENT.get_template('recreatedata.html')
    self.response.write(self.template.render(template_values))
        
app = webapp2.WSGIApplication([
    (r'/', MainPage),
    (r'/kanji', KanjiLookup),
    (r'/summary', KanjiSummary),
    (r'/recreatedata', RecreateData)
], debug=True)
