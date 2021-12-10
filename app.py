from flask import Flask, render_template, request, jsonify
import requests
from microservice import Microservice

import re
import json
from datetime import datetime

app = Flask(__name__)

connected_apps = set()
cache = {}


# Route for "/" (frontend):
@app.route('/')
def index():
    return render_template("index.html")

# Route for old (plain) frontend:
@app.route('/plain')
def index_plain():
    return render_template("index_plain.html")


@app.route('/microservice', methods=['PUT'])
def add_microservice():
    # Verify all required keys are present in JSON:
    required_keys = ['port', 'ip', 'name', 'creator', 'tile']
    for required_key in required_keys:
        if required_key not in request.json:
            return f'Required key {required_key} not present in payload JSON.', 400

        if isinstance(request.json, str):
            return f'Required key {required_key} has invalid type in payload JSON (should be str).', 400

    # Add the microservice:
    m = Microservice(
        request.json['ip'] + ':' + request.json['port'],
        request.json.get('dependencies', []),
        request.json['name'],
        request.json['creator'],
        request.json['tile'],
    )
    print('connection received from: ' + m.ip)
    connected_apps.add(m)

    return 'Success', 200


@app.route('/microservice', methods=['DELETE'])
def remove_microservice():
    print(f'delete request received from: {request.host}')
    previous_len = len(connected_apps)
    j = request.json

    if 'ip' not in j or 'port' not in j:
        return 'Invalid Input', 400

    ip = j['ip'] + ':' + j['port']
    m = Microservice(ip, [])

    connected_apps.discard(m)
    if len(connected_apps) == previous_len:
        return 'Not Found', 404

    return 'Success', 200


@app.route('/status', methods=["GET"])
def list_all_connected_services():
    status = [{
        'name': service.name,
        'creator': service.creator,
        'ip': service.ip,
        'dependencies': [depend.ip for depend in service.dependencies] if service.dependencies is not None else []
    } for service in connected_apps]

    return jsonify(status), 200


# Route for "/MIX" (middleware):
@app.route('/MIX', methods=["POST"])
def POST_MIX():
    global connected_apps
    # process form data
    location = request.form['location']

    match = re.match(r"\s*([+-]?([0-9]*[.])?[0-9]+)[,\s]+([+-]?([0-9]*[.])?[0-9]+)\s*", location)
    if match is None:
        return 'Invalid input', 400

    lat = float(match.group(1))
    lon = float(match.group(3))

    if abs(lat) > 90:
        return 'Invalid latitude', 400

    if abs(lon) > 180:
        return 'Invalid longitude', 400

    # aggregate JSON from all IMs
    r = []
    for im in connected_apps.copy():
        # get the IM response:
        try:
            j = process_request(im, lat, lon)
        except Exception as e:
            print(im)
            print(e)
            connected_apps.discard(im)
            continue

        # add metadata about the IM service:
        j.update({
            '_metadata': {
                'name': im.name,
                'creator': im.creator,
                'tile': im.tile,
                'max-age': im.max_age
            }
        })

        r.append(j)

    return jsonify(r), 200


def get_dependencies(dependency_info: [dict]) -> [Microservice]:
    """
    Convert a json list of dependencies into a list of Microservice objects,
    by searching for the appropriate Microservices in connected_apps.
    """
    dependency_list = []
    for dependency in dependency_info:
        # search for a matching IM
        if 'name' in dependency and 'creator' in dependency:
            for im in connected_apps:
                if im.name == dependency['name'] and im.creator == dependency['creator']:
                    dependency_list.append(im)
                    break
            else:
                raise ValueError('Dependency not found')
        elif 'ip' in dependency and 'port' in dependency:
            for im in connected_apps:
                if im.ip == dependency['ip'] + ':' + dependency['port']:
                    dependency_list.append(im)
                    break
            else:
                raise ValueError('Dependency not found')
        else:
            raise ValueError('Not enough dependency information')
    return dependency_list


def process_request(service: Microservice, lat: float, lon: float, visited=tuple()) -> dict:
    """
    Return the json output of a microservice, recursively calling this function for dependencies.
    Any cache hits will be returned.
    """
    # cache check
    if cache_hit((lat, lon), service):
        return cache[(lat, lon)][service.ip][0]

    # first time dependency search
    if service.dependencies is None:
        try:
            service.dependencies = get_dependencies(service.dependency_info)
        except ValueError as e:
            print(f'{e} for service {service.ip}')
            return {}

    # aggregate all dependency data (starting with lat, lon) and send as a request to our IM
    dependency_results = {'latitude': lat, 'longitude': lon}

    for dependency in service.dependencies:
        if dependency in visited:
            # check for circular dependencies
            print(f'Circular dependency: asking for {dependency} on top of {list(visited)}')
            return {}
        else:
            # concatenate results to dependency_results
            dependency_results.update(process_request(dependency, lat, lon, visited + (dependency,)))

    return make_im_request(service, dependency_results, lat, lon)


def make_im_request(service: Microservice, j: dict, lat: float, lon: float) -> dict:
    """
    Return the json response after a GET request to a service (with a json input j).
    """
    try:
        r = requests.get(service.ip, json=j, timeout=2)
    except requests.exceptions.RequestException:
        print(f'service {service.name} at {service.ip} not connecting. removed from MIX!')
        connected_apps.discard(service)
        return {}

    if 500 > r.status_code >= 400:
        print(f'service {service.name} at {service.ip} returned error code {str(r.status_code)}')
        return {}
    elif r.status_code >= 500:
        print(f'service {service.name} at {service.ip} returned error code {str(r.status_code)} - removed from MIX!')
        connected_apps.discard(service)
        return {}

    add_entry_to_cache((lat, lon), service, r)
    return r.json()


def parse_cache_header(header: str) -> float:
    """
    Return the age from a Cache-Control header string.
    raises ValueError if the Cache-Control is not recognized.
    """
    m = re.match(r"max-age=(\d+)", header)
    if m is None:
        raise ValueError
    return float(m.group(1))


def add_entry_to_cache(latlon: tuple, service: Microservice, response) -> None:
    """
    Add a microservice response to cache.
    """
    # set max_age for a service if it has not been set already
    if service.max_age is None:
        if 'Cache-Control' not in response.headers or 'max-age' not in response.headers['Cache-Control']:
            service.max_age = 0  # no cache
        else:
            try:
                service.max_age = parse_cache_header(response.headers['Cache-Control'])
            except ValueError:
                print(f'Bad Cache-Control for service {service.name} at {service.ip} - falling back to no-cache.')
                service.max_age = 0

    # enter the service response json into our cache
    if latlon not in cache:
        cache[latlon] = {service.ip: (response.json(), datetime.now())}
    else:
        cache[latlon][service.ip] = (response.json(), datetime.now())


def cache_hit(latlon: tuple, service: Microservice) -> bool:
    """
    Return whether a cached response is available.
    """
    if service.max_age == 0 or latlon not in cache or service.ip not in cache.get(latlon):
        print('cache miss! entry not in cache')
        return False

    curr_time = datetime.now()
    timediff = curr_time - cache[latlon][service.ip][1]

    if timediff.total_seconds() < service.max_age:
        print('cache hit!')
        return True
    print('cache miss! exceeded max_age')
    return False
