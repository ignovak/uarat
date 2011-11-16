#!/usr/bin/env python
#-*- coding: utf-8 -*-

import string, Cookie, sha, time, random, cgi, urllib, datetime, StringIO, pickle, uuid, hashlib, re, logging

from google.appengine.api import memcache
from google.appengine.ext import webapp, db
from django.utils import simplejson as json

from model import User, FofouUser, Forum, Topic, Post
import view

def xhr(handler):
  return handler.request.headers.get('X-Requested-With') == 'XMLHttpRequest'

class Signup(webapp.RequestHandler):
  def get(self):
    template_values = {
      'form' : [
        {
          'label': 'Nickname',
          'type': 'text',
          'name': 'nickname',
          'value': self.request.get('nickname')
        },
        {
          'label': 'Email',
          'type': 'text',
          'name': 'email',
          'value': self.request.get('email')
        },
        {
          'label': 'Password',
          'type': 'password',
          'name': 'password',
        },
        {
          'label': 'Confirm password',
          'type': 'password',
          'name': 'confirmPassword',
        },
        {
          'label': 'Name',
          'type': 'text',
          'name': 'username',
          'value': self.request.get('username')
        }
      ]
    }
    page = view.Signup(self.request, template_values)
    page.render(self.response.out)

  def post(self):
    self.nickname = self.request.get('nickname')
    self.email = self.request.get('email')
    self.password = self.request.get('password')
    self.confirmPassword = self.request.get('confirmPassword')
    self.username = self.request.get('username')

    salt = str(uuid.uuid4()).replace('-','')
    passwordHash = hashlib.sha1(self.password + salt).hexdigest()

    key = User(
      nickname = self.nickname,
      email = self.email,
      password = str(passwordHash),
      salt = salt,
      username = self.username
    ).put()

    uid = key.id()
    sid = str(uuid.uuid4()).replace('-','')
    memcache.set(sid, uid, 36000)
    self.response.headers.add_header('Set-Cookie',
        'sid=%s; path=/' % sid)

    if xhr(self):
      resp = {
        'username': self.username,
        'uid': uid
      }
      return self.response.out.write(json.dumps(resp))
    else:
      self.redirect('/')

class Login(webapp.RequestHandler):
  ERROR_CODES = {
    'wrongEmail': 'Email is incorrect'
  }
  def get(self):
    template_values = {
      # 'error': self.ERROR_CODES.get(self.request.get('error'), 'Some error')
      'error': self.request.get('error'),
    }
    page = view.Login(self.request, template_values)
    page.render(self.response.out)

  def post(self):
    error = self.__error()
    if error:
      if xhr(self):
        return self.response.out.write('{"error":"' + error + '"}')
      else:
        return self.redirect('/login?error=' + error)

    sid = str(uuid.uuid4()).replace('-','')
    uid = self.user.key().id()
    memcache.set(sid, uid, 36000)
    self.response.headers.add_header('Set-Cookie',
        'sid=%s; path=/' % sid)

    if xhr(self):
      role = 'user admin' if self.user.is_admin else 'user'
      resp = {
        'role': role,
        'username': self.user.username,
        'uid': uid
      }
      return self.response.out.write(json.dumps(resp))
    else:
      self.redirect('/')

  def __error(self):
    email_or_nickname = self.request.get('name')
    if re.match('^[-.\w]+@(?:[a-z\d][-a-z\d]+\.)+[a-z]{2,6}$', email_or_nickname) is not None:
      self.user = User.all().filter('email =', email_or_nickname).get()
    elif re.match('^\w*$', email_or_nickname) is not None:
      self.user = User.all().filter('nickname =', email_or_nickname).get()
    else:
      return 'incorrectEmailOrNickname'

    if self.user is None:
      return 'wrongEmailOrNickname'

    salt = self.user.salt
    password = self.request.get('password')

    # temp: allow login without password
    if password == 'password':
      return
    if re.match('^\w+$', password) is None:
      password = ''
    passwordHash = hashlib.sha1(password + salt).hexdigest()

    if self.user.password != passwordHash:
      return 'wrongPassword'

class Logout(webapp.RequestHandler):
  def get(self):
    sid = self.request.cookies.get('sid')
    memcache.delete(sid)
    self.response.headers.add_header('Set-Cookie', 'sid=; path=/')

    if self.request.headers.get('X-Requested-With') != 'XMLHttpRequest':
      self.redirect('/')

class Image(webapp.RequestHandler):
  def get(self, id):
    user = User.get_by_id(int(id))
    if user.avatar:
      self.response.headers['Content-Type'] = 'image/png'
      self.response.out.write(user.avatar)
    else:
      self.error(404)

