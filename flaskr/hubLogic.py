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
import os

dir = os.path.dirname(__file__)
serviceKey = os.path.join(dir, 'serviceAccountKey.json')
cred = credentials.Certificate(serviceKey)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://musicapp-a40f1.firebaseio.com/'
})
db = firebase_admin.db



REDIRECT_URI = 'soundhub://callback'
S_CLIENT_ID = '5a7e235500fe40509dee5c659b63f316'
S_CLIENT_SECRET = 'e551e52e22fa4caeacc4874a1c6a2fa9'

bp = Blueprint('hubs', __name__, url_prefix='/hubs')

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
    temp = []
    if request.method == 'GET':
        ids = db.reference('/hubs').get()
        for value in ids.values():
            temp.append(value)
        print(ids.values())
        return jsonify(temp)

@bp.route('/addHub', methods=('GET', 'POST'))
def createNewHub():
    ''' creates new Hub with given hubInformation,
    inclduing coordinate and (other stuff TBA) '''
    if request.method == 'POST':
        lat = request.form['lat']
        lng = request.form['lng']
        userId = request.form['userId']
        ref = db.reference('/hubs').push({
            'latlng': {
                'latitude': lat,
                'longitude': lng
            }

            # other stuff about hub, Possibly
            # Max Users, Genre of Music to be played, etc.
        })
        hubId = ref.path.split('/').pop()
        ref.child('songQueue').set({'userCount': 0})
        ref.child('artistQueue').set({'userCount': 0})
        ref.child('recentlyPlayed')
        db.reference('/users/{}/accountInfo'.format(userId)).update({ 'hostingHubId': hubId })
        return hubId

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


def getArtistName(artistId):
    userId = 'LqqarxhRAPhVF9CQcnSRtGzhSKS2'
    refreshToken = db.reference('/users/{}/accountInfo/tokens/RefreshToken'.format(userId)).get()
    accessToken = exchangeTokens(refreshToken)
    headers = {
        'Authorization': 'Bearer ' + accessToken
    }
    response = requests.get('https://api.spotify.com/v1/artists/{}'.format(artistId), headers=headers)
    return response.json()['name']


def getTrackName(trackId):
    userId = 'LqqarxhRAPhVF9CQcnSRtGzhSKS2'
    refreshToken = db.reference('/users/{}/accountInfo/tokens/RefreshToken'.format(userId)).get()
    accessToken = exchangeTokens(refreshToken)
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
    hubId = '-LH8wf5yTvXLbKeonupq'  # request.form['hub_id']should also ask for the HUB ID, that is stored in the map data
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

@bp.route('/getNextSong', methods=('GET', 'POST'))
def getNextSong():
    hubId = request.form['hubId']
    data =  db.reference('/hubs/{}'.format(hubId)).get()
    songDict = data['songQueue']
    artistDict = data['artistQueue']
    recentlyPlayed =  db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).get()
    userCount = songDict['userCount']
    temp = {}
    for key in songDict.keys():
        if key != 'userCount':
            temp[key] = [songDict[key][0], getRating(songDict[key], userCount)] #make a new dict with keys of id, -> artist,rating
    final = (applyArtistWeight(temp, artistDict, userCount))
    nextSong = max(final.keys(), key=(lambda key: final[key][1]))
    if recentlyPlayed:
        while nextSong in recentlyPlayed.keys():
            del final[nextSong]
            nextSong = max(final.keys(), key=(lambda key: final[key][1]))
        incrementRecentlyPlayed(hubId)
    db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).update({ nextSong: 0 })
    return jsonify(getTrackName(nextSong))

def incrementRecentlyPlayed(hubId, maxHistoryLength = 19): #up to 20 (maxHistoryLength + 1) songs will be remembered before replaying songs
    recents = db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).get()
    temp = {}
    for key in recents.keys():
        if recents[key] <= maxHistoryLength:
            temp[key] = recents[key] + 1
    print (temp)
    db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).set(temp)
    return

def getRating(data, userCount): #gets rating of song/artists by array of values
    total = 1
    for item in data:
        if type(item) == float or type(item) == int:
            total = total*item
    return total**(1/userCount)

def applyArtistWeight(toApply, Artists, userCount): #takes a dict, and a dict of artists weights and applys them to said dict
    for key in Artists.keys():
        for key2 in toApply.keys():
            if toApply[key2][0] == key:
                toApply[key2] = [toApply[key2][0], getRating(Artists[key], userCount) + toApply[key2][1]] #apply weights somehow
    return toApply