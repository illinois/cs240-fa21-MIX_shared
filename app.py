from flask import Flask, render_template, request, jsonify
import requests
from microservice import Microservice

import json
from datetime import datetime


app = Flask(__name__)

connected_apps = set()
processed = {}
cache = {}

# Route for "/" (frontend):
@app.route('/')
def index():
  return render_template("index.html")

@app.route('/microservice', methods=['PUT'])
def add_microservice():
  # Verify all required keys are present in JSON:
  requiredKeys = ['port', 'ip', 'name', 'creator', 'tile']
  for requiredKey in requiredKeys:
    if requiredKey not in request.json:
      return f'Required key {requiredKey} not present in payload JSON.', 400

  # Add the microservice:
  dependency_list = convert_dependencies_to_objects(request.json['dependencies'])
  m = Microservice(
    request.json['ip'] + ':' + request.json['port'],
    dependency_list,
    request.json['name'],
    request.json['creator'],
    request.json['tile'],
  )
  print('connection received from: ' + m.ip)
  connected_apps.add(m)

  return 'Success', 200

def convert_dependencies_to_objects(dependencies):
  dp_list = []
  for x in dependencies:
    # recursively fetch dependency lists where necessary
    if list(x['dependencies']) != list():
      dp_list.append(Microservice(x['ip'] + ':' + x['port'], convert_dependencies_to_objects(x['dependencies'])))
    else:
      dp_list.append(Microservice(x['ip'] + ':' + x['port'], []))
  
  return dp_list


@app.route('/microservice', methods=['DELETE'])
def remove_microservice():
  print('connection received from: ' + (request.host))
  for app in connected_apps:
    if app.ip == request.host:
      connected_apps.remove(app)
      break

  return 'Success', 200


# Route for "/MIX" (middleware):
@app.route('/MIX', methods=["POST"])
def POST_MIX():
  # process form data
  location = request.form['location']
  s = location.split(',')
  lat = float(s[0])
  lon = float(s[1])

  if abs(lat) > 90 or abs(lon) > 90:
    return 'Invalid input', 400

  # clear list of processed requests from connected apps
  processed.clear()

  # aggregate JSON from all IMs
  r = []
  for app in connected_apps:
    # create a response with the metadata about the IM service:
    j = {
      '_metadata': {
        'name': app.name,
        'creator': app.creator,
        'tile': app.tile,
      }
    }

    # add the IM response:
    if cache_hit((lat, lon), app):
      j.update( cache[(lat, lon)][app.ip][0] )
    else:
      j.update( process_request(app, lat, lon) )

    r.append(j)

  return jsonify(r), 200

def process_request(service: Microservice, lat: float, lon: float) -> dict:
  # if we've already processed an IM, we're finished
  if service.ip in processed:
    return processed[service.ip]

  if len(service.dependencies) == 0:
    # send a request to each service
    r = requests.get(service.ip, json={'latitude': lat, 'longitude': lon})
  else:
    # aggregate all dependency data and send as a request to our IM
    dependency_json = get_dependency_data(service, lat, lon)
    r = requests.get(service.ip, json=dependency_json)

  # if an IM returns a 400/500 level response, evaluate it as an empty JSON schema
  if r.status_code >= 400:
    print('service ' + service.ip + ' returned error code ' + str(r.status_code))
    return {}

  add_entry_to_cache((lat, lon), service, r)
  processed[service.ip] = r.json()
  return r.json()


def get_dependency_data(service: Microservice, lat: float, lon: float) -> dict:
  j = {}
  for dependency in service.dependencies:
    # handle dependencies which have their own dependencies recursively
    if len(dependency.dependencies) > 0:
      for dd in dependency.dependencies:
        j.update(get_dependency_data(dd, lat, lon))

    else:
      # if we've already made a request to this IM, just fetch from our processed requests dict
      if dependency.ip in processed:
        j.update(processed[dependency.ip])
      else:
        # make new request to IM
        r = requests.get(dependency.ip, json={'latitude': lat, 'longitude': lon})
        if r.status_code >= 400:
          print('service ' + service.ip + ' returned error code ' + str(r.status_code))
          continue

        add_entry_to_cache((lat, lon), dependency, r)
        processed[service.ip] = r.json()
        j.update(r.json())       

  return j

def parse_cache_header(header: str) -> int:
  return float(header.split('=')[1])

def add_entry_to_cache(latlon: tuple, service: Microservice, response) -> None:
  # set max_age for a service if it has not been set already
  if service.max_age == 0:
    service.max_age = parse_cache_header(response.headers['Cache-Control'])
  
  # enter the service response json into our cache
  if latlon not in cache:
    cache[latlon] = {service.ip : (response.json(), datetime.now())}
  else:
    cache[latlon][service.ip] = (response.json(), datetime.now())

def cache_hit(latlong: tuple, service: Microservice) -> bool:
  if service.max_age == 0 or latlong not in cache or service.ip not in cache.get(latlong):
    print('cache miss! entry not in cache')
    return False
  
  curr_time = datetime.now()
  timediff = curr_time - cache[latlong][service.ip][1]

  if timediff.total_seconds() < service.max_age:
    print('cache hit!')
    return True

  print('cache miss! exceeded max_age')
  return False