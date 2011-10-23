#!/usr/bin/env python
#-*- coding: utf-8 -*-

import logging, re

from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from BeautifulSoup import BeautifulSoup

class FetchUsers(webapp.RequestHandler):

  def get(self, id):
    url = 'http://uarat.3bb.ru/profile.php?id='
    self.response.headers['Content-Type'] = 'text-plain'
    # if 1:
    #   i = 3
    if id:
      r = range(int(id), int(id) + 1)
    else:
      r = range(21, 31)
    for i in r:
      res = urlfetch.fetch(url + str(i))
      user = self.__get_attributes(res) or {}
      logging.info(i)
      logging.info(user)
      for attr in user:
        # logging.info(attr + ': ' + user[attr])
        self.response.out.write('%s: %s\n' % (attr, user[attr]))
      self.response.out.write('\n\n')

  def __get_attributes(self, res):
    if res.status_code != 200:
      return

    main = BeautifulSoup(res.content)('div', id='viewprofile')
    if len(main) == 0:
      return

    profile_str = str(main[0])
    profile_str = profile_str \
                  .replace('Настоящее имя:', 'username') \
                  .replace('Пол:', 'sex') \
                  .replace('Возраст:', 'birthday') \
                  .replace('Местонахождение:', 'location') \
                  .replace('Зарегистрирован:', 'registered') \
                  .replace('Провел на форуме:', 'on_board') \
                  .replace('ICQ:', 'icq') \
                  .replace('Skype:', 'skype') \
                  .replace('Mail Agent:', 'mail_agent') \
                  .replace('Обо мне:', 'about') \
                  .replace('Интересы:', 'interests')
    
    profile = BeautifulSoup(profile_str)
    # self.response.out.write(profile.extract())
    # return
    fields = [
      'nickname',
      'rolename',
      'username',
      'sex',
      'birthday',
      'location',
      'registered',
      'avatar',
      'signature',
      'icq',
      'skype',
      'mail_agent',
      'about',
      'interests'
    ]

    lis = profile('li')
    nickname = lis.pop(0).strong.string
    rolename = lis.pop(0).strong.string
    avatar = lis.pop(0)
    signature = profile('div', id='profile-signature')

    attributes = dict(map(lambda li: (li.span and li.span.string, li.strong.string), lis))
    attributes['nickname'] = nickname
    attributes['rolename'] = rolename
    attributes['avatar'] = avatar.div and avatar.div.img['src']
    # TODO: fix signature retrieving
    # attributes['signature'] = signature and str(signature[0]('p')[0])
    attributes['signature'] = signature and signature[0]('p')[0].string

    user = {}
    for attr in fields:
      if attributes.get(attr):
        user[attr] = attributes[attr]
        if attr == 'birthday':
          user[attr] = re.search(r'\((.*)\)', user[attr]).group(1)
    return user

def main():
  application = webapp.WSGIApplication([
        ('/admin/fetch-users/(\d*)', FetchUsers)
        ], debug=True)
  util.run_wsgi_app(application)

if __name__ == '__main__':
  main()
