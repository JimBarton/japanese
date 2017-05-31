#!/usr/bin/python -tt
#coding=utf-8

import os
import re
import sys
import cgi

from google.appengine.api import app_identity
import cloudstorage as gcs
import webapp2
import jinja2

import jdatabase

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class MainPage(webapp2.RequestHandler):
  def get(self):

    # create the database tables and populate
    #self.do_setup()

    template = JINJA_ENVIRONMENT.get_template('index.html')
    self.response.write(template.render())


  def do_setup(self):
    kanji = jdatabase.Jkanji()

    # open a connection to the database
    db = jdatabase.Jdatabase()

    # create the database tables from scratch
    db.create_tables()
    
    # read the kanjidic file from the cloud storage if running in deployment
    # otherwise read from local file (can't get the stubs to work at the moment)
    if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
      bucket_name = os.environ.get('BUCKET_NAME', app_identity.get_default_gcs_bucket_name())
      bucket = '/' + bucket_name
    else:
      bucket = '.'

    filename = bucket + '/kanjidic2.xml'
    
    # If running in deployment then open file using google cloud library
    # otherwise use local file in this directory. cloud library should work but doesn't at the moment
    #if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
      #with gcs.open(filename) as kanji_file:
    #else:
    with open(filename) as kanji_file:
      # read each line in the kanji file and extract each kanji and its data based on tags
      for line in kanji_file:
        search = re.search(r'<literal>(.+)</literal>',line)
        if search:
          kanji.dict['id'] = search.group(1)
          continue
        search = re.search(r'<grade>(\d+)</grade>', line)
        if search:
          kanji.dict['grade'] = search.group(1)
          continue
        search = re.search(r'<stroke_count>(\d+)</stroke_count>', line)
        if search and not kanji.dict['strokecount']:
          kanji.dict['strokecount'] = search.group(1)
          continue
        search = re.search(r'<freq>(\d+)</freq>', line)
        if search:
          kanji.dict['frequency'] = search.group(1)
          continue
        search = re.search(r'<jlpt>(\d+)</jlpt>', line)
        if search:
          kanji.dict['jlpt'] = search.group(1)
          continue
        search = re.search(r'</character>', line)
        if search:
          # we have reached the end of one kanji tag
          # if this is a jouyou kanji, write out the current kanji to the database
          if (kanji.dict['grade'] >= '1' and kanji.dict['grade'] <= '8'):
            db.insert_kanji(kanji)
          # reset the string variables for the next kanji
          kanji.dict['id'] = ''
          kanji.dict['grade'] = ''
          kanji.dict['strokecount'] = ''
          kanji.dict['frequency'] = ''
          kanji.dict['jlpt'] = ''

    db.close_connection()

class DisplayKanji(webapp2.RequestHandler):
  def post(self):
    # open a connection to the database
    db = jdatabase.Jdatabase()

    kanji_id = cgi.escape(self.request.get('content'))
    kanji_template = db.retrieve_kanji(kanji_id)
    print kanji_template
    template = JINJA_ENVIRONMENT.get_template('displaykanji.html')
    self.response.write(template.render(kanji_template.dict))

    db.close_connection()
        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/displaykanji', DisplayKanji)
], debug=True)
