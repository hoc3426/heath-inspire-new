'''A module to return records from INSPIRE.'''

import sys
from requests import Session
from requests.exceptions import ConnectTimeout, HTTPError, RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

YOUR_EMAIL = 'hoc@fnal.gov'
URL = 'https://labs.inspirehep.net/api/literature'
HEADERS = {'Accept': 'application/json', 'User-Agent': YOUR_EMAIL}
LIMIT = {'size': 250}

def get_records(url=None, payload=None, headers=None):
    """ yield json of record(s) matching query """

    connection_timeout = 20
    with Session() as session:
        retry_strategy = Retry(total=5,
                               backoff_factor=2,
                               status_forcelist=[429, 500, 502, 503, 504],
                               method_whitelist=["GET", "POST"])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.headers = headers
        try:
            response = session.get(url, params=payload,
                                   timeout=connection_timeout)
            response.raise_for_status()
        except ConnectTimeout as error:
            print('Timeout accessing {0}\n{1}'.format(url, error))
            sys.exit(0)
        except HTTPError as error:
            print('HTTPError accessing {0}\n{1}'.format(url, error))
            sys.exit(0)
        except RequestException as error:
            print('Error accessing {0}\n{1}'.format(url, error))
            sys.exit(0)

        for rec in response.json().get(u'hits').get(u'hits'):
            yield rec
        while u'next' in response.links:
            nexturl = response.links.get(u'next').get(u'url')
            if nexturl:
                try:
                    response = session.get(nexturl, params=payload,
                                           timeout=connection_timeout)
                    response.raise_for_status()
                except ConnectTimeout as error:
                    print('Timeout accessing {0}\n{1}'.format(nexturl, error))
                    sys.exit(0)
                except HTTPError as error:
                    print('HTTPError accessing {0}\n{1}'.format(nexturl, error))
                    sys.exit(0)
                except RequestException as error:
                    print('Error accessing {0}\n{1}'.format(nexturl, error))
                    sys.exit(0)
                for rec in response.json().get(u'hits').get(u'hits'):
                    yield rec

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
    args.update({'q': search})
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
