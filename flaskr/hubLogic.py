import requests
import base64
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from urllib.parse import urlencode
from flask import (
    Blueprint, redirect, request, jsonify, abort
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
S_CLIENT_ID = 'cb443358fc6f47fc8b82c129cbb70440'
S_CLIENT_SECRET = 'c357352a9115423495a8be6b79fb26c1'

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

@bp.route('/getAccessToken', methods=('GET', 'POST'))
def getAccToken():
    userId = request.form['userId']
    refreshToken = db.reference('/users/{}/RefreshToken'.format(userId)).get()
    response = jsonify(exchangeTokens(refreshToken))
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

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
        response = jsonify({"hubId": hubId})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

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
    refreshToken = db.reference('/users/{}/RefreshToken'.format(userId)).get()
    accessToken = exchangeTokens(refreshToken)
    headers = {
        'Authorization': 'Bearer ' + accessToken
    }
    response = requests.get('https://api.spotify.com/v1/artists/{}'.format(artistId), headers=headers)
    return response.json()['name']

def getTrackName(trackId, userId):
    refreshToken = db.reference('/users/{}/RefreshToken'.format(userId)).get()
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
    hubId = request.form['hub_id']
    refreshToken = db.reference('/users/{}/RefreshToken'.format(userId)).get()
    accessToken = exchangeTokens(refreshToken)

    # queueRef.transaction(lambda snapshot: updateSongs(snapshot))
    # return 'completed'

    songList = {}
    data = getUserData(accessToken, recentlyPlayedURL)
    for i in range(len(data.keys())):  # gets all recently played track IDs
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
    for i in range(len(data['items'])):  # gets all track ids of short term
        trackId = data['items'][i]['id']
        if trackId in songList.keys():
            songList[trackId][1] += rankWeight * multiplier
        else:
            songList[trackId] = [data['items'][i]['artists'][0]['id'], rankWeight * multiplier]
        rankWeight -= .02

    rankWeight = 2
    multiplier = 1.5
    data = getUserData(accessToken, favoritesURL + 'tracks', 'medium_term')
    for i in range(len(data['items'])):
        trackId = data['items'][i]['id']
        if trackId in songList.keys():
            songList[trackId][1] += rankWeight * multiplier
        else:
            songList[trackId] = [data['items'][i]['artists'][0]['id'], rankWeight * multiplier]
        rankWeight -= .02

    rankWeight = 2
    multiplier = 1
    data = getUserData(accessToken, favoritesURL + 'tracks', 'long_term')
    for i in range(len(data['items'])):
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
    for i in range(len(data['items'])):
        artistId = data['items'][i]['id']
        if artistId in artistList.keys():
            artistList[artistId] += rankWeight * multiplier
        else:
            artistList[artistId] = rankWeight * multiplier
        rankWeight -= .02

    rankWeight = 2
    multiplier = 1.5
    data = getUserData(accessToken, favoritesURL + 'artists', 'medium_term')
    for i in range(len(data['items'])):
        artistId = data['items'][i]['id']
        if artistId in artistList.keys():
            artistList[artistId] += rankWeight * multiplier
        else:
            artistList[artistId] = rankWeight * multiplier
        rankWeight -= .02

    rankWeight = 2
    multiplier = 1
    data = getUserData(accessToken, favoritesURL + 'artists', 'long_term')
    for i in range(len(data['items'])):
        artistId = data['items'][i]['id']
        if artistId in artistList.keys():
            artistList[artistId] += rankWeight * multiplier
        else:
            artistList[artistId] = rankWeight * multiplier
        rankWeight -= .02

    db.reference('/hubs/{}/artistQueue'.format(hubId)).transaction(lambda snapshot: updateArtists(snapshot, artistList))
    response = jsonify({"TEXT" : 'Finished Processing the Data!'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
    # get user data from spotify
    # parse through data and add to hub

def getTrackInfo(userId, trackId):
    refreshToken = db.reference('/users/{}/RefreshToken'.format(userId)).get()
    accessToken = exchangeTokens(refreshToken)
    headers = {
        'Authorization': 'Bearer ' + accessToken
    }
    response = requests.get('https://api.spotify.com/v1/tracks/{}'.format(trackId), headers=headers)
    return response.json()

@bp.route('/deleteHub', methods=('GET', 'POST'))
def deleteHub():
    hubId = request.form['hubId']
    userId = request.form['userId']
    db.reference('/users/{}/accountInfo/hostingHubId'.format(userId)).delete()
    db.reference('/hubs/{}'.format(hubId)).delete()

@bp.route('/getRecentlyPlayed', methods=('GET', 'POST'))
def getRecents():
    userId = request.form['userId']
    hubId = request.form['hubId']
    recents = db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).get()
    if recents:
        response = jsonify(getTrackInfo(userId, min(recents.keys(), key=(lambda key: recents[key]))))
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    else:
        abort(500)

@bp.route('/getNextSong', methods=('GET', 'POST'))
def getNextSong():
    userId = request.form['userId']
    hubId = request.form['hubId']
    data =  db.reference('/hubs/{}'.format(hubId)).get()
    songDict = data['songQueue']
    artistDict = data['artistQueue']
    recentlyPlayed =  db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).get()
    userCount = songDict['userCount']
    if userCount == 0:
        abort(500)
    temp = {}
    for key in songDict.keys():
        if key != 'userCount':
            temp[key] = [songDict[key][0], getRating(songDict[key], userCount)] #make a new dict with keys of id, -> artist,rating
    final = (applyArtistWeight(temp, artistDict, userCount))
    temp = {}
    for key in final.keys():
        temp[final[key][1]] = getTrackName(key, userId)
    a = []
    for key in temp.keys():
        a.append([key, temp[key]])
    a.sort()
    print(a)
    # return (jsonify(temp))
    nextSong = max(final.keys(), key=(lambda key: final[key][1]))
    if recentlyPlayed:
        while nextSong in recentlyPlayed.keys():
            del final[nextSong]
            nextSong = max(final.keys(), key=(lambda key: final[key][1]))
        incrementRecentlyPlayed(hubId)
    db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).update({ nextSong: 0 })
    response = jsonify(getTrackInfo(userId, nextSong))
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

def incrementRecentlyPlayed(hubId, maxHistoryLength = 19): #up to 20 (maxHistoryLength + 1) songs will be remembered before replaying songs
    recents = db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).get()
    temp = {}
    for key in recents.keys():
        if recents[key] <= maxHistoryLength:
            temp[key] = recents[key] + 1
    db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).set(temp)
    return

@bp.route('/getPreviousSong', methods=('GET', 'POST'))
def getPreviousSong():
    hubId = request.form['hubId']
    userId = request.form['userId']
    recents = db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).get()
    recents = decrementRecentlyPlayed(hubId)
    return jsonify(getTrackInfo(userId, min(recents.keys(), key=(lambda key: recents[key]))))

def decrementRecentlyPlayed(hubId):
    recents = db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).get()
    temp = {}
    for key in recents.keys():
        if recents[key] != 0: 
            temp[key] = recents[key] - 1
    db.reference('/hubs/{}/recentlyPlayed'.format(hubId)).set(temp)
    return temp

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

