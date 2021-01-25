'''A module to return records from INSPIRE.'''

from requests import Session
from retrying import retry

YOUR_EMAIL = 'hoc@fnal.gov'
URL = 'https://labs.inspirehep.net/api/literature'
HEADERS = {'Accept': 'application/json', 'User-Agent': YOUR_EMAIL}
LIMIT = {'size': 250}

@retry(wait_random_min=1000, wait_random_max=2000, stop_max_attempt_number=7)
def get_records(url=None, payload=None, headers=None, session=None,
                nextlink=None):

    """ yield json of record(s) matching query """

    if url is None and nextlink is None:
        return None
    if session is None:
        session = Session()
        session.headers.update(headers)
    if nextlink is not None:
        response=session.get(nextlink)
    elif url is not None:
        response = session.get(url, params=payload)
    response.raise_for_status()
    resjson = response.json()
    hits = resjson.get('hits')
    for rec in hits.get('hits'):
        yield rec
    links = resjson.get('links')
    if 'next' in links:
        for nextrec in get_records(session=session, nextlink=links['next']):
            yield nextrec
    return True


def get_json_records(records):
    """ take records and reduce to a dictionary of recids and years """

    recid_list = []
    for record in records:
        recid_list.append(record)
        #recid = record['id']
        #try:
        #    rec_year_dict[recid] = REC_YEAR_DICT[recid]
        #except KeyError:
        #    rec_year_dict[recid] = int(record['metadata']['earliest_date'][:4])
    return recid_list

def get_result(search, fields=None):
    """ contruct a search and send it off to INSPIRE """

    args = dict(LIMIT)
    #args.update({'q':quote(search)})
    args.update({'q':search})
    if fields:
        args.update({'fields':fields})
    records = get_records(URL, payload=args, headers=HEADERS)
    return get_json_records(records)

def get_result_ids(search):
    """ get a list of recids """

    ids = []
    for record in get_result(search, 'ids'):
        ids.append(record['id'])
    return ids
