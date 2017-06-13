#!/usr/bin/python -tt
#coding=utf-8

import os
import sys
import cgi
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
          
#open a connection to the database
db = jdatabase.Jdatabase()

class MainPage(webapp2.RequestHandler):
  """ Class for the main page which is actually currently the kanji lookup page with no
      currently selected kanji
  """
  template = JINJA_ENVIRONMENT.get_template('index.html')

  def get(self):
    """ Render a the lookup page with no selected kanji, requesting input from user """
    self.response.write(self.template.render())

  def post(self):
    """ Retrieve the kanji character input by the user and get the corresponding entry from
         the database. Add this to the appengine memory cache for easy retrieval and then
         redirect to the lookup page for this kanji which has a dynamic URL of the kanji utf8
         in ascii form
    """
    kanji_literal = cgi.escape(self.request.get('lookup'))
    kanji_dict = db.retrieve_kanji(kanji_literal)
    try:
      added = memcache.set_multi(kanji_dict)
      if not added:
        logging.error('Memcache set failed %s', added)
    except ValueError:
      logging.error('Memcache set failed - data larger than 1MB')
    self.redirect("/kanji/"+repr(kanji_literal)[3:-1])

class KanjiLookup(webapp2.RequestHandler):
  """ Class for displaying results of kanji lookup. Allows user to perform various operations
      on the displayed data """
  template = JINJA_ENVIRONMENT.get_template('index.html')
  get_keys = ['vocab_list','id','literal','grade','strokecount','frequency','jlpt','known','style']

  def get(self, kanji_id):
    """ Get the current kanji from the memory cache and render it """
    current_data = memcache.get_multi(self.get_keys)
    logging.info(current_data)
    current_data['vocab_display_list'] = db.retrieve_kanji_vocab(current_data['literal'])
    print 'current_data'
    print current_data
    self.response.write(self.template.render(current_data))

  def post(self, kanji_id):
    """ Retrieve any input from the user and update data accordingly"""
    current_data = memcache.get_multi(self.get_keys)
    logging.info(current_data)
    # If this is a new kanji lookup then retrieve it from the database and add it to memory cache
    if 'lookup' in self.request.POST:
      kanji_literal = cgi.escape(self.request.get('lookup'))
      kanji_dict = db.retrieve_kanji(kanji_literal)
      try:
        added = memcache.set_multi(kanji_dict)
        if not added:
          logging.error('Memcache set failed %s', added)
      except ValueError:
        logging.error('Memcache set failed - data larger than 1MB')
      self.redirect("/kanji/"+repr(kanji_literal)[3:-1])
    # If the user has updated this kanji 'known' status then reflect this in the current kanji data
    elif 'known' in self.request.POST:
      current_data['known'] = True
    elif 'unknown' in self.request.POST:
      current_data['known'] = False
    db.update_known_status(current_data)
    current_data['vocab_display_list'] = db.retrieve_kanji_vocab(current_data['literal'])
    
    # render the current kanji
    self.response.write(self.template.render(current_data))

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
    (r'/kanji/(.+)', KanjiLookup),
    (r'/recreatedata', RecreateData)
], debug=True)
