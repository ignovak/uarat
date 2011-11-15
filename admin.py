#!/usr/bin/env python
#-*- coding: utf-8 -*-

import logging, re
from datetime import datetime

from google.appengine.api import urlfetch
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util

from BeautifulSoup import BeautifulSoup
from model import User

class FetchUsers(webapp.RequestHandler):

  def get(self):
    url = 'http://uarat.3bb.ru/profile.php?id='
    self.response.headers['Content-Type'] = 'text-plain'
    start = int(self.request.get('s') or 0) + 1
    end = int(self.request.get('e') or 10) + 1

    users = []
    for i in range(start, end):
      res = urlfetch.fetch(url + str(i))
      user = self.__get_attributes(res)
      if user:
        users.append(user)

    db.put(users)
    self.response.out.write('done')

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
                  .replace('Женский', 'female') \
                  .replace('Мужской', 'male') \
                  .replace('Возраст:', 'birthday') \
                  .replace('Местонахождение:', 'location') \
                  .replace('Зарегистрирован:', 'registered') \
                  .replace('Провел на форуме:', 'on_board') \
                  .replace('ICQ:', 'icq') \
                  .replace('Skype:', 'skype') \
                  .replace('Mail Agent:', 'mail_agent') \
                  .replace('Обо мне:', 'about') \
                  .replace('Сообщений:', 'posts_num') \
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
      'posts_num',
      'interests'
    ]

    lis = profile('li')
    nickname = lis.pop(0).strong.string
    rolename = lis.pop(0).strong.string
    avatar = lis.pop(0)
    signature = profile('div', id='profile-signature')

    def get_attr(li):
      if li.span:
        if li.span.string == 'posts_num':
          return ('posts_num', re.search('\d+', str(li.strong)).group())
        return (li.span and li.span.string, li.strong.string)
      return ('', '')

    attributes = dict(map(get_attr, lis))

    attributes['nickname'] = nickname
    attributes['rolename'] = rolename
    attributes['avatar'] = avatar.div and avatar.div.img['src']
    attributes['signature'] = signature and signature[0]('p')[0]

    user = User()
    for key in fields:
      val = attributes.get(key)
      if val:
        if key == 'birthday':
          birthday = re.search(r'\((.*)\)', val).group(1)
          user.birthday = datetime.strptime(birthday, '%Y-%m-%d').date()
        elif key == 'registered':
          user.registered = datetime.strptime(val, '%Y-%m-%d').date()
        elif key == 'posts_num':
          user.posts_num = int(val)
        else:
          user.__dict__['_' + key] = unicode(val)
    return user

class RemoveUsers(webapp.RequestHandler):
  def get(self):
    db.delete(User.all(keys_only=True))

class Help(webapp.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('''
    /admin/fetch-users?s=0&e=10
    /admin/remove-users
    ''')


def main():
  application = webapp.WSGIApplication([
        ('/admin/fetch-users', FetchUsers),
        ('/admin/remove-users', RemoveUsers),
        ('/admin.*', Help)
        ], debug=True)
  util.run_wsgi_app(application)

if __name__ == '__main__':
  main()
