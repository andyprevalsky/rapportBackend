import requests
import base64
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from urllib.parse import urlencode
from flask import (
    Blueprint, redirect, request, jsonify
)
import json

cred = credentials.Certificate('/Users/engrbundle/Desktop/flask-tutorial/flaskr/serviceAccountKey.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://musicapp-a40f1.firebaseio.com/'
})
db = firebase_admin.db

REDIRECT_URI = 'soundhub://callback'
S_CLIENT_ID = '5a7e235500fe40509dee5c659b63f316'
S_CLIENT_SECRET = 'e551e52e22fa4caeacc4874a1c6a2fa9'

bp = Blueprint('hubs', __name__, url_prefix='/hubs')

hubs = {  # this dict will most likely be stored in a SQL table, or possible firebase
    '11111': {  # hubID stored as key for Hub

    },
    'xxxxx': {

    },
    'yyyyy': {

    }  # , etc.
}


def exchangeTokens(refreshToken):
    body = {
        'grant_type': 'refresh_token',
        'refresh_token': refreshToken
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + (base64.b64encode((S_CLIENT_ID + ':' + S_CLIENT_SECRET).encode())).decode()
    }
    response = requests.post('https://accounts.spotify.com/api/token', data=urlencode(body), headers=headers)
    return (response.json()["access_token"])


def getUserData(accessToken, url, time_range=None):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Bearer ' + accessToken
    }
    body = {
        'limit': 50
    }
    if time_range:
        body['time_range'] = time_range

    response = requests.get(url, headers=headers, params=urlencode(body))
    return response.json()

@bp.route('/getHubs/', methods=('GET', 'POST'))
def getHubInfo():
    if request.method == 'GET':
        ref = db.reference('/hubs/')
        return json.dumps(ref.get())

@bp.route('/addHub', methods=('GET', 'POST'))
def createNewHub():
    ''' creates new Hub with given hubInformation,
    inclduing coordinate and (other stuff TBA) '''

    if request.method == 'GET':
        ref = db.reference('/hubs').push({
            'coordinates': 'placeholder'
            # 'coordinates': request.form['coordinates']
            # other stuff about hub, Possibly
            # Max Users, Genre of Music to be played, etc.
        })
        hubId = ref.path.split('/').pop()
        ref.child('songQueue').set({'userCount': 0})
        ref.child('artistQueue').set({'userCount': 0})
        return ref.path


def updateSongs(snapshot, songList):
    snapshot['userCount'] += 1
    for key in songList:
        if key in snapshot.keys():
            snapshot[key].append(songList[key][1])
        else:
            snapshot[key] = songList[key]
    return snapshot


def updateArtists(snapshot, artistList):
    snapshot['userCount'] += 1
    for key in artistList:
        if key in snapshot.keys():
            snapshot[key].append(artistList[key])
        else:
            snapshot[key] = [artistList[key]]
    return snapshot


def getArtistName(artistId, accessToken):
    headers = {
        'Authorization': 'Bearer ' + accessToken
    }
    response = requests.get('https://api.spotify.com/v1/artists/{}'.format(artistId), headers=headers)
    return response.json()['name']


def getTrackName(trackId, accessToken):
    headers = {
        'Authorization': 'Bearer ' + accessToken
    }
    response = requests.get('https://api.spotify.com/v1/tracks/{}'.format(trackId), headers=headers)
    return response.json()['name']


@bp.route('/addUser', methods=('GET', 'POST'))
def addUser():
    ''' adds a User to a new hub, requires the
        userID and hubID (tentative requirements) '''
    if request.method == 'GET':
        return 'used for testing purposes only'

    recentlyPlayedURL = 'https://api.spotify.com/v1/me/player/recently-played'
    favoritesURL = 'https://api.spotify.com/v1/me/top/'
    userId = request.form['user_id']
    hubId = '-LGvh2r8o0pISqGd3YqT'  # request.form['hub_id']should also ask for the HUB ID, that is stored in the map data
    refreshToken = db.reference('/users/{}/accountInfo/tokens/RefreshToken'.format(userId)).get()
    accessToken = exchangeTokens(refreshToken)

    # queueRef.transaction(lambda snapshot: updateSongs(snapshot))
    # return 'completed'

    songList = {}
    data = getUserData(accessToken, recentlyPlayedURL)
    for i in range(50):  # gets all recently played track IDs
        trackId = data['items'][i]['track']['id']
        if trackId in songList.keys():
            songList[trackId][1] += 1
        else:
            songList[trackId] = [data['items'][i]['track']['artists'][0]['id'], 1]

    for key in list(songList):
        if songList[key] == 1:
            del songList[key]

    # recentMultiPlayed is now populated with keys of every songs played
    # more than once and how many times they have been played

    rankWeight = 2
    multiplier = 2
    data = getUserData(accessToken, favoritesURL + 'tracks', 'short_term')
    for i in range(50):  # gets all track ids of short term
        trackId = data['items'][i]['id']
        if trackId in songList.keys():
            songList[trackId][1] += rankWeight * multiplier
        else:
            songList[trackId] = [data['items'][i]['artists'][0]['id'], rankWeight * multiplier]
        rankWeight -= .02

    rankWeight = 2
    multiplier = 1.5
    data = getUserData(accessToken, favoritesURL + 'tracks', 'medium_term')
    for i in range(50):
        trackId = data['items'][i]['id']
        if trackId in songList.keys():
            songList[trackId][1] += rankWeight * multiplier
        else:
            songList[trackId] = [data['items'][i]['artists'][0]['id'], rankWeight * multiplier]
        rankWeight -= .02

    rankWeight = 2
    multiplier = 1
    data = getUserData(accessToken, favoritesURL + 'tracks', 'long_term')
    for i in range(50):
        trackId = data['items'][i]['id']
        if trackId in songList.keys():
            songList[trackId][1] += rankWeight * multiplier
        else:
            songList[trackId] = [data['items'][i]['artists'][0]['id'], rankWeight * multiplier]
        rankWeight -= .02

    db.reference('/hubs/{}/songQueue'.format(hubId)).transaction(lambda snapshot: updateSongs(snapshot, songList))

    artistList = {}

    rankWeight = 2
    multiplier = 2
    data = getUserData(accessToken, favoritesURL + 'artists', 'short_term')
    for i in range(50):
        artistId = data['items'][i]['id']
        if artistId in artistList.keys():
            artistList[artistId] += rankWeight * multiplier
        else:
            artistList[artistId] = rankWeight * multiplier
        rankWeight -= .02

    rankWeight = 2
    multiplier = 1.5
    data = getUserData(accessToken, favoritesURL + 'artists', 'medium_term')
    for i in range(50):
        artistId = data['items'][i]['id']
        if artistId in artistList.keys():
            artistList[artistId] += rankWeight * multiplier
        else:
            artistList[artistId] = rankWeight * multiplier
        rankWeight -= .02

    rankWeight = 2
    multiplier = 1
    data = getUserData(accessToken, favoritesURL + 'artists', 'long_term')
    for i in range(50):
        artistId = data['items'][i]['id']
        if artistId in artistList.keys():
            artistList[artistId] += rankWeight * multiplier
        else:
            artistList[artistId] = rankWeight * multiplier
        rankWeight -= .02

    db.reference('/hubs/{}/artistQueue'.format(hubId)).transaction(lambda snapshot: updateArtists(snapshot, artistList))

    return ('Finished Processing the Data!')
    # get user data from spotify
    # parse through data and add to hub