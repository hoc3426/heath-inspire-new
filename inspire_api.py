'''A module to return records from INSPIRE.'''

from requests import Session
from retrying import retry

from inspire_api_constants_private import COOKIE, TOKEN

YOUR_EMAIL = 'hoc@fnal.gov'
URL = 'https://labs.inspirehep.net/api/'
DOMAIN = 'inspirehep.net'
HEADERS = {'Accept': 'application/json', 'User-Agent': YOUR_EMAIL,
           'Authorization': f'Bearer {TOKEN}'}
LIMIT = {'size': 250}

@retry(wait_random_min=1000, wait_random_max=2000, stop_max_attempt_number=7)
def get_records(url=None, payload=None, headers=None, session=None,
                nextlink=None):

    ''' yield generator of record(s) matching query '''

    if url is None and nextlink is None:
        return None
    if session is None:
        session = Session()
        session.cookies.set('session', COOKIE, 
                            domain=DOMAIN, secure=True)
        session.headers.update(headers)
    if nextlink is not None:
        response=session.get(nextlink)
    elif url is not None:
        response = session.get(url, params=payload)
    response.raise_for_status()
    resjson = response.json()
    hits = resjson.get('hits', {})
    if url is not None:
        yield hits.get('total', 0)
    for rec in hits.get('hits', {}):
        yield rec
    links = resjson.get('links', {})
    if 'next' in links:
        for nextrec in get_records(session=session, nextlink=links['next']):
            yield nextrec
    return True


import requests
from backoff import expo, on_exception

YOUR_EMAIL = 'hoc@fnal.gov'
INSPIRE_LITERATURE_API_ENDPOINT = 'https://labs.inspirehep.net/api/literature'
SIZE = 250

session = requests.Session()
session.headers.update({'User-Agent': f'INSPIRE API Client ({YOUR_EMAIL})'})
session.headers.update({'Authorization' : f'Token {TOKEN}'})

CONECTION_ERRORS = (requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError)

@on_exception(expo, CONECTION_ERRORS, max_tries=10)
def perform_inspire_literature_search(query, fields=()):
    '''Perform the search query on INSPIRE.
    Args:
        query (str): the search query to get the results for.
        fields (iterable): a list of fields to return.
    Yields:
        dict: the json response for every record.
    '''
    params={'q': query, 'fields': ','.join(fields)}
    params['size'] = SIZE

    response = session.get(INSPIRE_LITERATURE_API_ENDPOINT, params=params)
    response.raise_for_status()
    content = response.json()

    for result in content['hits']['hits']:
        yield result['metadata']

    while 'next' in content.get('links', {}):
        response = session.get(content['links']['next'])
        response.raise_for_status()
        content = response.json()

        for result in content['hits']['hits']:
            yield result['metadata']


def get_json_records(records):
    ''' take generator object of records and return a list of records '''

    count = 0
    total = next(records)
    record_list = []
    for count, record in enumerate(records, 1):
        record_list.append(record)
    if count != total:
        print(f'Warning: total={total} count={count}')
        #return None
    return record_list

def get_result(search, fields=None, collection='literature'):
    ''' contruct a search and send it off to INSPIRE '''

    args = dict(LIMIT)
    if isinstance(search, int) or search.isdigit():
        search = f'recid:{search}'
    args.update({'q':search})
    if fields:
        args.update({'fields':fields})
    url = URL + collection
    records = get_records(url, payload=args, headers=HEADERS)
    #records = perform_inspire_literature_search(search, fields=())
    result = get_json_records(records)
    if result is None:
        print(f'Problem with the search: {search}')
        return None
    return result

def get_result_ids(search, collection='literature'):
    ''' get a list of recids '''

    ids = []
    result = get_result(search=search, fields='ids',
                        collection=collection)
    if not result:
        #print(f'No result for {search}')
        return []
    for record in result:
        ids.append(record['id'])
    return ids
