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

class MainPage(webapp2.RequestHandler):
  def get(self):
    template = JINJA_ENVIRONMENT.get_template('index.html')
    self.response.write(template.render())

  def post(self):
    # open a connection to the database
    db = jdatabase.Jdatabase()

    kanji_id = cgi.escape(self.request.get('content'))
    kanji_template = db.retrieve_kanji(kanji_id)
    print kanji_template
    template = JINJA_ENVIRONMENT.get_template('index.html')
    self.response.write(template.render(kanji_template.dict))

    db.close_connection()

class RecreateData(webapp2.RequestHandler):
  def get(self):
    template = JINJA_ENVIRONMENT.get_template('recreatedata.html')
    self.response.write(template.render())

  def post(self):
    # open a connection to the database
    db = jdatabase.Jdatabase()
    db.recreate_tables()
    db.close_connection()

    template_values = {'flag':True}
    template = JINJA_ENVIRONMENT.get_template('recreatedata.html')
    self.response.write(template.render(template_values))
        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/recreatedata', RecreateData)
], debug=True)
