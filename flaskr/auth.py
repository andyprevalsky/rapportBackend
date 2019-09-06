import functools
import requests
import json
import base64
from urllib.parse import urlencode
from flask import (
    Blueprint, redirect, request, jsonify
)

REDIRECT_URI = 'http://localhost:3000/'
S_CLIENT_ID = 'cb443358fc6f47fc8b82c129cbb70440'
S_CLIENT_SECRET = 'c357352a9115423495a8be6b79fb26c1'


bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/newToken', methods=('GET', 'POST'))
def grabToken():
  body = {
    'code': '',
    'redirect_uri': REDIRECT_URI,
    'grant_type': 'authorization_code'
  }
  headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': 'Basic ' + (base64.b64encode((S_CLIENT_ID+':'+S_CLIENT_SECRET).encode())).decode()
  }

  if request.method == 'POST':
    body['code'] = request.form['code']
    response = requests.post('https://accounts.spotify.com/api/token', data=urlencode(body), headers=headers)
    response = jsonify(response.json())
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
  return ('NO POST')

def exchangeTokens(refreshToken):
  body = {
    'grant_type': 'refresh_token',
    'refresh_token': refreshToken
  }
  headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': 'Basic ' + (base64.b64encode((S_CLIENT_ID+':'+S_CLIENT_SECRET).encode())).decode()
  }
  response = requests.post('https://accounts.spotify.com/api/token', data=urlencode(body), headers=headers)
  return (response.json()["access_token"])

@bp.route('/refreshToken', methods=('GET', 'POST'))
def refreshToken():
  body = {
    'grant_type': 'refresh_token',
    'refresh_token': ''
  }
  headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': 'Basic ' + (base64.b64encode((S_CLIENT_ID+':'+S_CLIENT_SECRET).encode())).decode()
  }
  if request.method == 'POST':
    response = requests.post('https://accounts.spotify.com/api/token', data=urlencode(body), headers=headers)
    response = jsonify(response.json())
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
  return ('NO POST')

