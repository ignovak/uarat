#!/usr/bin/env python
#-*- coding: utf-8 -*-

from google.appengine.ext import db

class User(db.Model):
  nickname = db.StringProperty()
  email = db.EmailProperty()
  show_email = db.BooleanProperty()
  password = db.StringProperty()
  remember_me = db.BooleanProperty()
  salt = db.StringProperty()
  username = db.StringProperty()
  location = db.StringProperty(default='')
  sex = db.StringProperty(choices=['male', 'female'])
  birthday = db.DateProperty()
  interests = db.StringProperty(default='')
  about = db.TextProperty()
  icq = db.StringProperty(default='')
  skype = db.StringProperty(default='')
  # mail_agent = db.StringProperty(default='')
  avatar = db.StringProperty()
  show_avatar = db.BooleanProperty()
  signature = db.TextProperty()

  is_admin = db.BooleanProperty(default=False)

class FofouUser(db.Model):
  # according to docs UserProperty() cannot be optional, so for anon users
  # we set it to value returned by anonUser() function
  # user is uniquely identified by either user property (if not equal to
  # anonUser()) or cookie
  user = db.UserProperty()
  cookie = db.StringProperty()
  # email, as entered in the post form, can be empty string
  email = db.StringProperty()
  # name, as entered in the post form
  name = db.StringProperty()
  # homepage - as entered in the post form, can be empty string
  homepage = db.StringProperty()
  # value of 'remember_me' checkbox selected during most recent post
  remember_me = db.BooleanProperty(default=True)

class Forum(db.Model):
  GROUPES = ['About rats', 'Nurseries', 'Ad board', 'Other', 'Techical']
  # Urls for forums are in the form /<urlpart>/<rest>
  url = db.StringProperty(required=True)
  # What we show as html <title> and as main header on the page
  title = db.StringProperty()
  # a tagline is below title
  tagline = db.StringProperty()
  # stuff to display in left sidebar
  sidebar = db.TextProperty()
  # if true, forum has been disabled. We don't support deletion so that
  # forum can always be re-enabled in the future
  is_disabled = db.BooleanProperty(default=False)
  # just in case, when the forum was created. Not used.
  created_on = db.DateTimeProperty(auto_now_add=True)
  # name of the skin (must be one of SKINS)
  skin = db.StringProperty()
  # Google analytics code
  analytics_code = db.StringProperty()
  # Note: import_secret is obsolete
  import_secret = db.StringProperty()
  group = db.StringProperty(choices=set(GROUPES))

# A forum is collection of topics
class Topic(db.Model):
  forum = db.Reference(Forum, required=True)
  subject = db.StringProperty(required=True)
  created_on = db.DateTimeProperty(auto_now_add=True)
  # name of person who created the topic. Duplicates Post.user_name
  # of the first post in this topic, for speed
  created_by = db.StringProperty()
  # just in case, not used
  updated_on = db.DateTimeProperty(auto_now=True)
  # True if first Post in this topic is deleted. Updated on deletion/undeletion
  # of the post
  is_deleted = db.BooleanProperty(default=False)
  # ncomments is redundant but is faster than always quering count of Posts
  ncomments = db.IntegerProperty(default=0)

# A topic is a collection of posts
class Post(db.Model):
  topic = db.Reference(Topic, required=True)
  forum = db.Reference(Forum, required=True)
  created_on = db.DateTimeProperty(auto_now_add=True)
  message = db.TextProperty(required=True)
  sha1_digest = db.StringProperty(required=True)
  # admin can delete/undelete posts. If first post in a topic is deleted,
  # that means the topic is deleted as well
  is_deleted = db.BooleanProperty(default=False)
  # ip address from which this post has been made
  user_ip_str = db.StringProperty(required=False)
  # user_ip is an obsolete value, only used for compat with entries created before
  # we introduced user_ip_str. If it's 0, we assume we'll use user_ip_str, otherwise
  # we'll user user_ip
  user_ip = db.IntegerProperty(required=True)

  user = db.Reference(User, required=True)
  # user_name, user_email and user_homepage might be different than
  # name/homepage/email fields in user object, since they can be changed in
  # FofouUser
  user_name = db.StringProperty()
  user_email = db.StringProperty()
  user_homepage = db.StringProperty()

