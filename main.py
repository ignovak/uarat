# This code is in Public Domain. Take all the code you want, we'll just write more.
import os, string, Cookie, sha, time, random, cgi, urllib, datetime, StringIO, pickle, uuid, hashlib, re
import logging

import wsgiref.handlers
# from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template
from django.utils import feedgenerator
from django.template import Context, Template

from model import User, FofouUser, Forum, Topic, Post
from offsets import *

# Structure of urls:
#
# Top-level urls
#
# / - list of all forums
#
# /manageforums[?forum=<key> - edit/create/disable forums
#
# Per-forum urls
#
# /<forum_url>/[?from=<n>]
#    index, lists of topics, optionally starting from topic <n>
#
# /<forum_url>/post[?id=<id>]
#    form for creating a new post. if "topic" is present, it's a post in
#    existing topic, otherwise a post starting a new topic
#
# /<forum_url>/topic?id=<id>&comments=<comments>
#    shows posts in a given topic, 'comments' is ignored (just a trick to re-use
#    browser's history to see if the topic has posts that user didn't see yet
#
# /<forum_url>/postdel?<post_id>
# /<forum_url>/postundel?<post_id>
#    delete/undelete post
#
# /<forum_url>/rss
#    rss feed for first post in the topic (default)
#
# /<forum_url>/rssall
#    rss feed for all posts

# HTTP codes
HTTP_NOT_ACCEPTABLE = 406
HTTP_NOT_FOUND = 404

RSS_MEMCACHED_KEY = "rss"

def rss_memcache_key(forum):
  return RSS_MEMCACHED_KEY + str(forum.key().id)

BANNED_IPS = {
    "59.181.121.8"  : 1,
    "62.162.98.194" : 1,
    "93.191.0.129"  : 1,
    #"127.0.0.1" : 1,
}

def my_hostname():
  # TODO: handle https as well
  h = "http://" + os.environ["SERVER_NAME"];
  port = os.environ["SERVER_PORT"]
  if port != "80":
      h += ":%s" % port
  return h

def xhr(handler):
  return handler.request.headers.get('X-Requested-With') == 'XMLHttpRequest'

SKINS = ["default"]

# cookie code based on http://code.google.com/p/appengine-utitlies/source/browse/trunk/utilities/session.py
FOFOU_COOKIE = "fofou-uid"
COOKIE_EXPIRE_TIME = 60*60*24*120 # valid for 60*60*24*120 seconds => 120 days

def get_user_agent(): return os.environ['HTTP_USER_AGENT']
def get_remote_ip(): return os.environ['REMOTE_ADDR']

def long2ip(val):
  slist = []
  for x in range(0,4):
    slist.append(str(int(val >> (24 - (x * 8)) & 0xFF)))
  return ".".join(slist)

def to_unicode(val):
  if isinstance(val, unicode): return val
  try:
    return unicode(val, 'latin-1')
  except:
    pass
  try:
    return unicode(val, 'ascii')
  except:
    pass
  try:
    return unicode(val, 'utf-8')
  except:
    raise

def to_utf8(s):
    s = to_unicode(s)
    return s.encode("utf-8")

def req_get_vals(req, names, strip=True): 
  if strip:
    return [req.get(name).strip() for name in names]
  else:
    return [req.get(name) for name in names]

def get_inbound_cookie():
  c = Cookie.SimpleCookie()
  cstr = os.environ.get('HTTP_COOKIE', '')
  c.load(cstr)
  return c

def new_user_id():
  sid = sha.new(repr(time.time())).hexdigest()
  return sid

def valid_user_cookie(c):
  # cookie should always be a hex-encoded sha1 checksum
  if len(c) != 40:
    return False
  # TODO: check that user with that cookie exists, the way appengine-utilities does
  return True

g_anonUser = None
def anonUser():
  global g_anonUser
  if None == g_anonUser:
    g_anonUser = users.User("dummy@dummy.address.com")
  return g_anonUser

def valid_forum_url(url):
  if not url:
    return False
  try:
    return url == urllib.quote_plus(url)
  except:
    return False

def sanitize_homepage(s):
    'prevent javascript injection'
    if not (s.startswith("http://") or s.startswith("https://")):
        return ""
    # 'http://' is the default value we put, so if unchanged, consider it
    # as not given at all
    if s == "http://": return ""
    return s

def valid_email(txt):
  '''
  very simplistic check for <txt> being a valid e-mail address
  allow empty strings
  '''
  if not txt:
    return True
  if '@' not in txt:
    return False
  if '.' not in txt:
    return False
  return True

def forum_from_url(url):
  assert '/' == url[0]
  path = url[1:]
  if '/' in path:
    (forumurl, rest) = path.split("/", 1)
  else:
    forumurl = path
  return Forum.gql("WHERE url = :1", forumurl).get()
      
def forum_root(forum): return "/" + forum.url + "/"

def forum_siteroot_tmpldir_from_url(url):
  assert '/' == url[0]
  path = url[1:]
  if '/' in path:
    (forumurl, rest) = path.split("/", 1)
  else:
    forumurl = path
  forum = Forum.gql("WHERE url = :1", forumurl).get()
  if not forum:
    return (None, None, None)
  siteroot = forum_root(forum)
  skin_name = forum.skin
  if skin_name not in SKINS:
    skin_name = SKINS[0]
  tmpldir = os.path.join("skins", skin_name)
  return (forum, siteroot, tmpldir)

def get_log_in_out(url):
  user = users.get_current_user()
  if user:
    if users.is_current_user_admin():
      return "Welcome admin, %s! <a href=\"%s\">Log out</a>" % (user.nickname(), users.create_logout_url(url))
    else:
      return "Welcome, %s! <a href=\"%s\">Log out</a>" % (user.nickname(), users.create_logout_url(url))
  else:
    return "<a href=\"%s\">Log in or register</a>" % users.create_login_url(url)    

class FofouBase(webapp.RequestHandler):
  def user(self):
    self.username = ''
    self.role = ''
    self.is_admin = False
    sessionId = self.request.cookies.get('sid')
    if sessionId:
      userId = memcache.get(sessionId)
      if userId is not None:
        user = User.get_by_id(userId)
        self.username = user.name
        if user.is_admin:
          self.is_admin = True
          self.role = 'user admin'
        else:
          self.role = 'user'
        return user

  _cookie = None
  # returns either a FOFOU_COOKIE sent by the browser or a newly created cookie
  def get_cookie(self):
    if self._cookie != None:
      return self._cookie
    cookies = get_inbound_cookie()
    for cookieName in cookies.keys():
      if FOFOU_COOKIE != cookieName:
        del cookies[cookieName]
    if (FOFOU_COOKIE not in cookies) or not valid_user_cookie(cookies[FOFOU_COOKIE].value):
      cookies[FOFOU_COOKIE] = new_user_id()
      cookies[FOFOU_COOKIE]['path'] = '/'
      cookies[FOFOU_COOKIE]['expires'] = COOKIE_EXPIRE_TIME
    self._cookie = cookies[FOFOU_COOKIE]
    return self._cookie

  _cookie_to_set = None
  # remember cookie so that we can send it when we render a template
  def send_cookie(self):
    if None == self._cookie_to_set:
      self._cookie_to_set = self.get_cookie()

  def get_cookie_val(self):
    c = self.get_cookie()
    return c.value

  def template_out(self, template_name, template_values):
    self.response.headers['Content-Type'] = 'text/html'
    if None != self._cookie_to_set:
      # a hack extract the cookie part from the whole "Set-Cookie: val" header
      c = str(self._cookie_to_set)
      c = c.split(": ", 1)[1]
      self.response.headers["Set-Cookie"] = c
    path = os.path.join(template_name)
    # path = os.path.join(os.path.dirname(__file__), template_name)
    # path = template_name
    #logging.info("tmpl: %s" % path)
    res = template.render(path, template_values)
    self.response.out.write(res)

class ManageForums(FofouBase):
  '''
  responds to GET /manageforums[?forum=<key>&disable=yes&enable=yes]
  and POST /manageforums with values from the form
  '''

  def post(self):
    self.user()
    if not self.is_admin:
      return self.redirect("/")

    forum_key = self.request.get('forum_key')
    forum = None
    if forum_key:
      forum = db.get(db.Key(forum_key))
      if not forum:
        # invalid key - should not happen so go to top-level
        return self.redirect("/")

    vals = ['url','title', 'tagline', 'sidebar', 'group', 'disable', 'enable', 'analyticscode']
    (url, title, tagline, sidebar, group, disable, enable, analytics_code) = req_get_vals(self.request, vals)

    if group not in Forum.GROUPES:
      # invalid group - should not happen so go to top-level
      return self.redirect("/")

    errmsg = None
    if not valid_forum_url(url):
      errmsg = "Url contains illegal characters"
    if not forum:
      forum_exists = Forum.gql("WHERE url = :1", url).get()
      if forum_exists:
        errmsg = "Forum with this url already exists"

    if errmsg:
      tvals = {
        'urlclass' : "error",
        'hosturl' : self.request.host_url,
        'prevurl' : url,
        'prevtitle' : title,
        'prevtagline' : tagline,
        'prevsidebar' : sidebar,
        'prevanalyticscode' : analytics_code,
        'forum_key' : forum_key,
        'errmsg' : errmsg
      }
      return self.render_rest(tvals)

    title_or_url = title or url
    if forum:
      # update existing forum
      forum.url = url
      forum.title = title
      forum.tagline = tagline
      forum.sidebar = sidebar
      forum.group = group
      forum.analytics_code = analytics_code
      forum.put()
      msg = "Forum '%s' has been updated." % title_or_url
    else:
      # create a new forum
      Forum(
        url=url,
        title=title,
        tagline=tagline,
        sidebar=sidebar,
        group=group,
        analytics_code=analytics_code
      ).put()
      msg = "Forum '%s' has been created." % title_or_url
    url = "/manageforums?msg=%s" % urllib.quote(to_utf8(msg))
    return self.redirect(url)

  def get(self):
    self.user()
    if not self.is_admin:
      return self.redirect("/")

    # if there is 'forum_key' argument, this is editing an existing forum.
    forum = None
    forum_key = self.request.get('forum_key')
    if forum_key:
      forum = db.get(db.Key(forum_key))
      if not forum:
        # invalid forum key - should not happen, return to top level
        return self.redirect("/")

    tvals = {
      'hosturl' : self.request.host_url,
      'forum' : forum,
      'groupes': Forum.GROUPES,
      'role': self.role,
      'username': self.username
    }
    if forum:
      forum.title_non_empty = forum.title or "Title."
      forum.sidebar_non_empty = forum.sidebar or "Sidebar." 
      disable = self.request.get('disable')
      enable = self.request.get('enable')
      if disable or enable:
        title_or_url = forum.title or forum.url
        if disable:
          forum.is_disabled = True
          forum.put()
          msg = "Forum %s has been disabled." % title_or_url
        else:
          forum.is_disabled = False
          forum.put()
          msg = "Forum %s has been enabled." % title_or_url
        return self.redirect("/manageforums?msg=%s" % urllib.quote(to_utf8(msg)))
    self.render_rest(tvals, forum)

  def render_rest(self, tvals, forum=None):
    # user = users.get_current_user()
    forumsq = db.GqlQuery("SELECT * FROM Forum")
    forums = []
    for f in forumsq:
      f.title_or_url = f.title or f.url
      edit_url = "/manageforums?forum_key=" + str(f.key())
      if f.is_disabled:
        f.enable_disable_txt = "enable"
        f.enable_disable_url = edit_url + "&enable=yes"
      else:
        f.enable_disable_txt = "disable"
        f.enable_disable_url = edit_url + "&disable=yes"      
      if forum and f.key() == forum.key():
        # editing existing forum
        f.no_edit_link = True
        tvals['prevurl'] = f.url
        tvals['prevtitle'] = f.title
        tvals['prevtagline'] = f.tagline
        tvals['prevsidebar'] = f.sidebar
        tvals['prevanalyticscode'] = f.analytics_code
        tvals['forum_key'] = str(f.key())
      forums.append(f)
    tvals['msg'] = self.request.get('msg')
    # tvals['user'] = user
    tvals['forums'] = forums
    if forum and not forum.tagline:
      forum.tagline = "Tagline."
    self.template_out("templates/manage_forums.html", tvals)

class ForumList(FofouBase):
  '''
  responds to /, shows list of available forums or redirects to
  forum management page if user is admin
  '''

  def get(self):
    self.user()
    # if users.is_current_user_admin():
    #   return self.redirect("/manageforums")
    MAX_FORUMS = 256 # if you need more, tough
    forums = Forum.all().fetch(MAX_FORUMS)
    # forums = db.GqlQuery("SELECT * FROM Forum").fetch(MAX_FORUMS)
    for f in forums:
      f.title_or_url = f.title or f.url

    forums = map(
      lambda group: {
        'title': group,
        'forums': filter(
          lambda forum: forum.group == group,
          forums
        )
      },
      Forum.GROUPES
    )
    tvals = {
      'forums' : forums,
      'role': self.role,
      'username': self.username,
      'groupes': Forum.GROUPES
    }
    self.template_out("templates/forum_list.html", tvals)

class PostDelUndel(webapp.RequestHandler):
  'responds to GET /postdel?<post_id> and /postundel?<post_id>'
  def get(self):
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.redirect("/")
    is_moderator = users.is_current_user_admin()
    if not is_moderator or forum.is_disabled:
      return self.redirect(siteroot)
    post_id = self.request.query_string
    #logging.info("PostDelUndel: post_id='%s'" % post_id)
    post = db.get(db.Key.from_path('Post', int(post_id)))
    if not post:
      logging.info("No post with post_id='%s'" % post_id)
      return self.redirect(siteroot)
    if post.forum.key() != forum.key():
      loggin.info("post.forum.key().id() ('%s') != fourm.key().id() ('%s')" % (str(post.forum.key().id()), str(forum.key().id())))
      return self.redirect(siteroot)
    path = self.request.path
    if path.endswith("/postdel"):
      if not post.is_deleted:
        post.is_deleted = True
        post.put()
        memcache.delete(rss_memcache_key(forum))
      else:
        logging.info("Post '%s' is already deleted" % post_id)
    elif path.endswith("/postundel"):
      if post.is_deleted:
        post.is_deleted = False
        post.put()
        memcache.delete(rss_memcache_key(forum))
      else:
        logging.info("Trying to undelete post '%s' that is not deleted" % post_id)
    else:
      logging.info("'%s' is not a valid path" % path)

    topic = post.topic
    # deleting/undeleting first post also means deleting/undeleting the whole topic
    first_post = Post.gql("WHERE forum=:1 AND topic = :2 ORDER BY created_on", forum, topic).get()
    if first_post.key() == post.key():
      if path.endswith("/postdel"):
        topic.is_deleted = True
      else:
        topic.is_deleted = False
      topic.put()

    # redirect to topic owning this post
    topic_url = siteroot + "topic?id=" + str(topic.key().id())
    self.redirect(topic_url)
    
class TopicList(FofouBase):
  '''
  responds to /<forumurl>/[?from=<from>]
  shows a list of topics, potentially starting from topic N
  '''

  def get_topics(self, forum, is_moderator, max_topics, cursor):
    # note: building query manually beccause gql() don't work with cursor
    # see: http://code.google.com/p/googleappengine/issues/detail?id=2757
    q = Topic.all()
    q.filter("forum =", forum)
    if not is_moderator:
        q.filter("is_deleted =", False)
    q.order("-created_on")
    if not cursor is None:
      q.with_cursor(cursor)
    topics = q.fetch(max_topics)
    new_cursor = q.cursor()
    if len(topics) < max_topics:
        new_cursor = None
    return (new_cursor, topics)

  def get(self):
    self.user()
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.redirect("/")
    cursor = self.request.get("from") or None
    is_moderator = False
    # is_moderator = users.is_current_user_admin()
    MAX_TOPICS = 75
    (new_cursor, topics) = self.get_topics(forum, is_moderator, MAX_TOPICS, cursor)
    forum.title_or_url = forum.title or forum.url
    tvals = {
      'role': self.role,
      'username': self.username,
      'siteroot' : siteroot,
      'siteurl' : self.request.url,
      'forum' : forum,
      'topics' : topics,
      'analytics_code' : forum.analytics_code or "",
      'new_from' : new_cursor
    }
    self.template_out('templates/topic_list.html', tvals)

class TopicForm(FofouBase):
  'responds to /<forumurl>/topic?id=<id>'

  def get(self):
    self.user()
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.redirect("/")
    forum.title_or_url = forum.title or forum.url

    topic_id = self.request.get('id')
    if not topic_id:
      return self.redirect(siteroot)

    topic = db.get(db.Key.from_path('Topic', int(topic_id)))
    if not topic:
      return self.redirect(siteroot)

    # is_moderator = users.is_current_user_admin()
    is_moderator = False
    if topic.is_deleted and not is_moderator:
      return self.redirect(siteroot)

    is_archived = False
    # Note: auto-archiving disabled
    #now = datetime.datetime.now()
    #week = datetime.timedelta(days=7)
    #week = datetime.timedelta(seconds=7)
    #if now > topic.created_on + week:
    #  is_archived = True

    # 200 is more than generous
    MAX_POSTS = 200
    if is_moderator:
      posts = Post.gql("WHERE forum = :1 AND topic = :2 ORDER BY created_on", forum, topic).fetch(MAX_POSTS)
    else:
      posts = Post.gql("WHERE forum = :1 AND topic = :2 AND is_deleted = False ORDER BY created_on", forum, topic).fetch(MAX_POSTS)

    if is_moderator:
      for p in posts:
        if 0 != p.user_ip:
          p.user_ip_str = long2ip(p.user_ip)
        if p.user_homepage:
          p.user_homepage = sanitize_homepage(p.user_homepage)

    tvals = {
      'role': self.role,
      'username': self.username,
      'siteroot' : siteroot,
      'forum' : forum,
      'analytics_code' : forum.analytics_code or "",
      'topic' : topic,
      'is_moderator' : is_moderator,
      'is_archived' : is_archived,
      'posts' : posts
    }
    tmpl = os.path.join("templates/topic.html")
    self.template_out(tmpl, tvals)

class RssFeed(webapp.RequestHandler):
  '''
  responds to /<forumurl>/rss, returns an RSS feed of recent topics
  (taking into account only the first post in a topic - that's what
  joelonsoftware forum rss feed does)
  '''

  def get(self):
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.error(HTTP_NOT_FOUND)

    cached_feed = memcache.get(rss_memcache_key(forum))
    if cached_feed is not None:
      self.response.headers['Content-Type'] = 'text/xml'
      self.response.out.write(cached_feed)
      return
      
    feed = feedgenerator.Atom1Feed(
      title = forum.title or forum.url,
      link = my_hostname() + siteroot + "rss",
      description = forum.tagline)
  
    topics = Topic.gql("WHERE forum = :1 AND is_deleted = False ORDER BY created_on DESC", forum).fetch(25)
    for topic in topics:
      title = topic.subject
      link = my_hostname() + siteroot + "topic?id=" + str(topic.key().id())
      first_post = Post.gql("WHERE topic = :1 ORDER BY created_on", topic).get()
      msg = first_post.message
      # TODO: a hack: using a full template to format message body.
      # There must be a way to do it using straight django APIs
      name = topic.created_by
      if name:
        t = Template("<strong>{{ name }}</strong>: {{ msg|striptags|escape|urlize|linebreaksbr }}")
      else:
        t = Template("{{ msg|striptags|escape|urlize|linebreaksbr }}")
      c = Context({"msg": msg, "name" : name})
      description = t.render(c)
      pubdate = topic.created_on
      feed.add_item(title=title, link=link, description=description, pubdate=pubdate)
    feedtxt = feed.writeString('utf-8')
    self.response.headers['Content-Type'] = 'text/xml'
    self.response.out.write(feedtxt)
    memcache.add(rss_memcache_key(forum), feedtxt)

class RssAllFeed(webapp.RequestHandler):
  '''
  responds to /<forumurl>/rssall, returns an RSS feed of all recent posts
  This is good for forum admins/moderators who want to monitor all posts
  '''

  def get(self):
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.error(HTTP_NOT_FOUND)

    feed = feedgenerator.Atom1Feed(
      title = forum.title or forum.url,
      link = my_hostname() + siteroot + "rssall",
      description = forum.tagline)
  
    posts = Post.gql("WHERE forum = :1 AND is_deleted = False ORDER BY created_on DESC", forum).fetch(25)
    for post in posts:
      topic = post.topic
      title = topic.subject
      link = my_hostname() + siteroot + "topic?id=" + str(topic.key().id())
      msg = post.message
      # TODO: a hack: using a full template to format message body.
      # There must be a way to do it using straight django APIs
      name = post.user_name
      if name:
        t = Template("<strong>{{ name }}</strong>: {{ msg|striptags|escape|urlize|linebreaksbr }}")
      else:
        t = Template("{{ msg|striptags|escape|urlize|linebreaksbr }}")
      c = Context({"msg": msg, "name" : name})
      description = t.render(c)
      pubdate = post.created_on
      feed.add_item(title=title, link=link, description=description, pubdate=pubdate)
    feedtxt = feed.writeString('utf-8')
    self.response.headers['Content-Type'] = 'text/xml'
    self.response.out.write(feedtxt)

class EmailForm(FofouBase):
  'responds to /<forumurl>/email[?post_id=<post_id>]'

  def get(self):
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.redirect("/")
    (num1, num2) = (random.randint(1,9), random.randint(1,9))
    post_id = self.request.get("post_id")
    if not post_id: return self.redirect(siteroot)
    post = db.get(db.Key.from_path('Post', int(post_id)))
    if not post: return self.redirect(siteroot)
    to_name = post.user_name or post.user_homepage
    subject = "Re: " + (forum.title or forum.url) + " - " + post.topic.subject
    forum.title_or_url = forum.title or forum.url
    tvals = {
      'siteroot' : siteroot,
      'forum' : forum,
      'post_id' : post_id,
      'to' : to_name,
      'subject' : subject,
      'log_in_out' : get_log_in_out(siteroot + "post")
    }
    tmpl = os.path.join(tmpldir, "email.html")
    self.template_out(tmpl, tvals)

  def post(self):
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.redirect("/")
    if self.request.get('Cancel'): self.redirect(siteroot)
    post_id = self.request.get("post_id")
    #logging.info("post_id = %s" % str(post_id))
    if not post_id: return self.redirect(siteroot)
    post = db.get(db.Key.from_path('Post', int(post_id)))
    if not post: return self.redirect(siteroot)
    topic = post.topic
    tvals = {
      'siteroot' : siteroot,
      'forum' : forum,
      'topic' : topic,
      'log_in_out' : get_log_in_out(siteroot + "post")
    }    
    tmpl = os.path.join(tmpldir, "email_sent.html")
    self.template_out(tmpl, tvals)

class PostForm(FofouBase):
  'responds to /<forumurl>/post[?id=<topic_id>]'

  def get(self):
    logging.info('get post')
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.redirect("/")

    self.send_cookie()

    rememberChecked = ""
    prevUrl = "http://"
    prevEmail = ""
    prevName = ""
    self.user()
    # if user and user.remember_me:
    #   rememberChecked = "checked"
    #   prevUrl = user.homepage
    #   if not prevUrl:
    #     prevUrl = "http://"
    #   prevName = user.name
    #   prevEmail = user.email
    forum.title_or_url = forum.title or forum.url
    tvals = {
      'role': self.role,
      'username': self.username,
      'layout': 'ajax.html' if xhr(self) else 'layout.html',
      'siteroot' : siteroot,
      'forum' : forum,
      'rememberChecked' : rememberChecked,
      'prevUrl' : prevUrl,
      'prevEmail' : prevEmail,
      'prevName' : prevName
    }
    topic_id = self.request.get('id')
    if topic_id:
      topic = db.get(db.Key.from_path('Topic', int(topic_id)))
      if not topic: return self.redirect(siteroot)
      tvals['prevTopicId'] = topic_id
      tvals['prevSubject'] = topic.subject
    tmpl = os.path.join('templates/post.html')
    self.template_out(tmpl, tvals)

  def post(self):
    user = self.user()
    if not user:
      return self.redirect('/?error=noUser')
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      logging.info('no forum')
      return self.redirect("/")
    if self.request.get('Cancel'): 
      logging.info('cancel')
      return self.redirect(siteroot)

    self.send_cookie()

    vals = ['TopicId', 'Subject', 'Message', 'Url']
    (topic_id, subject, message, homepage) = req_get_vals(self.request, vals)
    message = to_unicode(message)

    homepage = sanitize_homepage(homepage)
    tvals = {
      'role': self.role,
      'username': self.username,
      'siteroot' : siteroot,
      'forum' : forum,
      "prevSubject" : subject,
      "prevMessage" : message,
      "prevUrl" : homepage,
      "prevTopicId" : topic_id
    }
    
    # validate captcha and other values
    errclass = None
    if not message: errclass = "message_class"
    # first post must have subject
    if not topic_id and not subject: errclass = "subject_class"

    # sha.new() doesn't accept Unicode strings, so convert to utf8 first
    message_utf8 = message.encode('UTF-8')
    s = sha.new(message_utf8)
    sha1_digest = s.hexdigest()

    duppost = Post.gql("WHERE sha1_digest = :1", sha1_digest).get()
    if duppost: errclass = "message_class"

    if errclass:
      tvals[errclass] = "error"
      tmpl = os.path.join("templates/post.html")
      return self.template_out(tmpl, tvals)

    if not topic_id:
      topic = Topic(forum=forum, subject=subject, created_by=user.nickname)
      topic.put()
    else:
      topic = db.get(db.Key.from_path('Topic', int(topic_id)))
      #assert forum.key() == topic.forum.key()
      topic.ncomments += 1
      topic.put()

    user_ip_str = get_remote_ip()
    p = Post(topic=topic, forum=forum, user=user, user_ip=0, user_ip_str=user_ip_str, message=message, sha1_digest=sha1_digest, user_homepage = homepage)
    p.put()
    memcache.delete(rss_memcache_key(forum))
    if topic_id:
      logging.info('topic id')
      self.redirect(siteroot + "topic?id=" + str(topic_id))
    else:
      logging.info('no topic id')
      self.redirect(siteroot)

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
          'name': 'name',
          'value': self.request.get('name')
        }
      ],
      'layout': 'ajax.html' if xhr(self) else 'layout.html'
    }
    path = os.path.join('templates/signup.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
    self.nickname = self.request.get('nickname')
    self.email = self.request.get('email')
    self.password = self.request.get('password')
    self.confirmPassword = self.request.get('confirmPassword')
    self.name = self.request.get('name')

    salt = str(uuid.uuid4()).replace('-','')
    passwordHash = hashlib.sha1(self.password + salt).hexdigest()

    key = User(
      nickname = self.nickname,
      email = self.email,
      password = str(passwordHash),
      salt = salt,
      name = self.name
    ).put()

    sessionId = str(uuid.uuid4()).replace('-','')
    memcache.set(sessionId, key.id(), 36000)
    self.response.headers.add_header('Set-Cookie',
        'sid=%s; path=/' % sessionId)

    if xhr(self):
      resp = '{"username": "' + self.name + '"}'
      return self.response.out.write(resp)
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
      'layout': 'ajax.html' if xhr(self) else 'layout.html'
    }
    path = os.path.join('templates/login.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
    self.email = self.request.get('email')
    error = self.__error()
    if error:
      if xhr(self):
        return self.response.out.write('{"error":"' + error + '"}')
      else:
        return self.redirect('/login?error=' + error)

    sessionId = str(uuid.uuid4()).replace('-','')
    memcache.set(sessionId, self.user.key().id(), 36000)
    self.response.headers.add_header('Set-Cookie',
        'sid=%s; path=/' % sessionId)

    if xhr(self):
      role = 'user admin' if self.user.is_admin else 'user'
      resp = '{"role":"' + role + '", "username": "' + self.user.name + '"}'
      return self.response.out.write(resp)
    else:
      self.redirect('/')

  def __error(self):
    if re.match('^[-.\w]+@(?:[a-z\d][-a-z\d]+\.)+[a-z]{2,6}$', self.email) is None:
      return 'incorrectEmail'

    self.user = User.all().filter('email =', self.email).get()
    if self.user is None:
      return 'wrongEmail'

    salt = self.user.salt
    password = self.request.get('password')
    if re.match('^\w+$', password) is None:
      password = ''
    passwordHash = hashlib.sha1(password + salt).hexdigest()

    if self.user.password != passwordHash:
      return 'wrongPassword'

class Logout(webapp.RequestHandler):
  def get(self):
    sessionId = self.request.cookies.get('sid')
    memcache.delete(sessionId)
    self.response.headers.add_header('Set-Cookie', 'sid=; path=/')

    if self.request.headers.get('X-Requested-With') != 'XMLHttpRequest':
      self.redirect('/')

def main():
  application = webapp.WSGIApplication(
    [ ('/', ForumList),
      ('/manageforums', ManageForums),
      ('/signup', Signup),
      ('/login', Login),
      ('/logout', Logout),
      ('/[^/]+/postdel', PostDelUndel),
      ('/[^/]+/postundel', PostDelUndel),
      ('/[^/]+/post', PostForm),
      ('/[^/]+/topic', TopicForm),
      ('/[^/]+/email', EmailForm),
      ('/[^/]+/rss', RssFeed),
      ('/[^/]+/rssall', RssAllFeed),
      ('/[^/]+/?', TopicList)
    ],
    debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
