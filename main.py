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
current_kanji = {'id': '',
                 'literal': '',
                 'grade': '',
                 'strokecount': '',
                 'frequency': '',
                 'jlpt': '',
                 'known': '',
                 'style': ''}
          
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
    elif 'known' in self.request.POST:
      current_kanji['known'] = True
      db.set_kanji_known_flag(current_kanji['literal'], current_kanji['known'])
    elif 'unknown' in self.request.POST:
      current_kanji['known'] = False
      db.set_kanji_known_flag(current_kanji['literal'], current_kanji['known'])
      
    print "3"
    print current_kanji['vocab_list']
    #self.style_display(db)
    self.response.write(self.template.render(current_kanji))
    
    db.close_connection()

  def style_display(self, db):
    global current_kanji
    character_list = set([a for x in current_kanji['vocab_list'] for a in x[0]])
    print 'character_list'
    print character_list
    for character in character_list:
      kanji = db.retrieve_kanji(character)
      print 'kanji'
      print kanji
      new_string = '<span style="color:blue">' + kanji['kanji_id'] + '</span>'
      if kanji and kanji['kanji_known']:
        for elem, each_vocab in enumerate(current_kanji['vocab_list']):
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
    print template_values
    template = JINJA_ENVIRONMENT.get_template('recreatedata.html')
    self.response.write(template.render(template_values))
        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/recreatedata', RecreateData)
], debug=True)
