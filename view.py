#!/usr/bin/env python
#-*- coding: utf-8 -*-

import os

from google.appengine.ext.webapp import template
from django.utils import simplejson as json

class View():
  def __init__(self, request):
    pass

  def render(self, out):
    pass

class Signup(View):
  def __init__(self, request, params):
    self.params = params

    # xhr
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
      layout = 'ajax.html'
    else:
      layout = 'layout.html'

    self.params['layout'] = layout

  def render(self, out):
    path = os.path.join('templates/signup.html')
    out.write(template.render(path, self.params))

class Login(View):
  def __init__(self, request, params):
    self.params = params

    # xhr
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
      layout = 'ajax.html'
    else:
      layout = 'layout.html'

    self.params['layout'] = layout

  def render(self, out):
    path = os.path.join('templates/login.html')
    out.write(template.render(path, self.params))
