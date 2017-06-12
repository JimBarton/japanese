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

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
          
#open a connection to the database
db = jdatabase.Jdatabase()

class MainPage(webapp2.RequestHandler):
  template = JINJA_ENVIRONMENT.get_template('index.html')

  def get(self):
    self.response.write(self.template.render())

  def post(self):
    print self.request.POST
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

class KanjiLookup(webapp2.RequestHandler):
  template = JINJA_ENVIRONMENT.get_template('index.html')
  get_keys = ['vocab_list','id','literal','grade','strokecount','frequency','jlpt','known','style']

  def get(self, kanji_id):
    current_data = memcache.get_multi(self.get_keys)
    logging.info(current_data)
    current_data['vocab_display_list'] = db.retrieve_kanji_vocab(current_data['literal'])
    print 'current_data'
    print current_data
    self.response.write(self.template.render(current_data))

  def post(self, kanji_id):
    current_data = memcache.get_multi(self.get_keys)
    logging.info(current_data)
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
    elif 'known' in self.request.POST:
      current_data['known'] = True
    elif 'unknown' in self.request.POST:
      current_data['known'] = False
    db.update_known_status(current_data)
    current_data['vocab_display_list'] = db.retrieve_kanji_vocab(current_data['literal'])
    
    self.response.write(self.template.render(current_data))

class RecreateData(webapp2.RequestHandler):
  template = JINJA_ENVIRONMENT.get_template('recreatedata.html')

  def get(self):
    # open a connection to the database
    template_values = db.retrieve_status()
    self.response.write(self.template.render(template_values))

  def post(self):
    # open a connection to the database
    db.recreate_base_data()
    template_values = db.retrieve_status()
 
    template_values['flag'] = True
    print template_values
    template = JINJA_ENVIRONMENT.get_template('recreatedata.html')
    self.response.write(self.template.render(template_values))
        
app = webapp2.WSGIApplication([
    (r'/', MainPage),
    (r'/kanji/(.+)', KanjiLookup),
    (r'/recreatedata', RecreateData)
], debug=True)
