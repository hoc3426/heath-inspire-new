'''A module to return records from INSPIRE.'''

import requests
from backoff import expo, on_exception

from inspire_api_constants_private import TOKEN, YOUR_EMAIL

INSPIRE_API_ENDPOINT = 'https://inspirehep.net/api'
SIZE = '250'

session = requests.Session()
session.headers.update({'User-Agent': f'INSPIRE API Client ({YOUR_EMAIL})'})
session.headers.update({'Authorization' : f'Bearer {TOKEN}'})

CONECTION_ERRORS = (requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError)

@on_exception(expo, CONECTION_ERRORS, max_tries=10)
def get_record(input_value, collection='literature'):
    '''Get a single INSPIRE record based on url or recid.'''

    if isinstance(input_value, int) or input_value.isdigit():
        url = f'{INSPIRE_API_ENDPOINT}/{collection}/{input_value}'
    elif input_value.startswith(INSPIRE_API_ENDPOINT):
        url = input_value
    else:
        print(f'get_record: unrecognized input {input_value}')
        print('  Should be INSPIRE url or recid')
        return None
    response = session.get(url)
    response.raise_for_status()
    content = response.json()
    return content['metadata']


@on_exception(expo, CONECTION_ERRORS, max_tries=10)
def perform_inspire_collection_search(query, fields, collection='literature'):
    '''Perform the search query on INSPIRE.
    Args:
        query (str): the search query to get the results for.
        fields (iterable): a list of fields to return.
        collection (str): Literature by default
    Yields:
        The total of the result and then
        dict: the json response for every record.
    '''

    params={'q': query, 'fields': ','.join(fields),
            'size': SIZE}

    url = f'{INSPIRE_API_ENDPOINT}/{collection}'

    response = session.get(url, params=params)
    response.raise_for_status()
    content = response.json()
    yield content['hits']['total']

    for result in content['hits']['hits']:
        yield result['metadata']

    while 'next' in content.get('links', {}):
        response = session.get(content['links']['next'])
        response.raise_for_status()
        content = response.json()

        for result in content['hits']['hits']:
            yield result['metadata']

def get_result(search, fields=(), collection='literature'):
    '''Perform a search in a collection and bring back fields'''

    if isinstance(search, int) or search.isdigit():
        search = f'recid:{search}'

    records = perform_inspire_collection_search(search, fields, collection)

    total = next(records)

    count = 0
    record_list = []
    for count, record in enumerate(records, 1):
        record_list.append(record)
    if count != total:
        print(f'Warning: total={total} count={count}')
    return record_list

def get_result_ids(search, collection='literature'):
    ''' get a list of recids '''

    ids = []
    result = get_result(search, fields='ids', collection=collection)
    if not result:
        #print(f'No result for {search}')
        return []
    for record in result:
        ids.append(record['control_number'])
    return ids
