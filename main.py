#!/usr/bin/python -tt
#coding=utf-8

import os
import sys
import cgi

import webapp2
import jinja2

import jdatabase

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
current_kanji = {}

class MainPage(webapp2.RequestHandler):
  template = JINJA_ENVIRONMENT.get_template('index.html')
  
  def get(self):
    self.response.write(self.template.render())

  def post(self):
    # open a connection to the database
    db = jdatabase.Jdatabase()
    global current_kanji
    
    print self.request.POST
    if 'lookup' in self.request.POST:
      kanji_id = cgi.escape(self.request.get('lookup'))
      current_kanji = db.retrieve_kanji_with_vocab(kanji_id)
      self.style_known_kanji(db)
    elif 'known' in self.request.POST:
      current_kanji.dict['kanji_known'] = True
      db.set_kanji_known_flag(current_kanji.dict['kanji_id'], current_kanji.dict['kanji_known'])
    elif 'unknown' in self.request.POST:
      current_kanji.dict['kanji_known'] = False
      db.set_kanji_known_flag(current_kanji.dict['kanji_id'], current_kanji.dict['kanji_known'])
      
    print "3"
    print current_kanji['vocab_list']
    self.response.write(self.template.render(current_kanji))
    
    db.close_connection()

  def style_known_kanji(self, db):
    global current_kanji
    character_list = set([a for x in current_kanji['vocab_list'] for a in x[0]])
    for character in character_list:
      kanji = db.retrieve_kanji(character)
      if kanji and kanji['kanji_known']:
        for elem, each_vocab in enumerate(current_kanji['vocab_list']):
          new_string = '<span style="color:blue">' + kanji['kanji_id'] + '</span>'
          current_kanji['vocab_list'][elem][0] = current_kanji['vocab_list'][elem][0].replace(kanji['kanji_id'], new_string)
  
class RecreateData(webapp2.RequestHandler):
  def get(self):
    template = JINJA_ENVIRONMENT.get_template('recreatedata.html')
    self.response.write(template.render())

  def post(self):
    # open a connection to the database
    db = jdatabase.Jdatabase()
    db.recreate_base_data()
    template_values = db.retrieve_status()
    db.close_connection()

    template_values['flag'] = True
    template = JINJA_ENVIRONMENT.get_template('recreatedata.html')
    self.response.write(template.render(template_values))
        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/recreatedata', RecreateData)
], debug=True)
