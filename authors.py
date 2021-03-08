'''
A script to handle parsing of authors.
'''

from inspire_api import get_record

def get_orcid_from_author(author):
    '''Get recid if you have the author.'''

    try:
        url = author['record']['$ref']
    except KeyError:
        return None
    jrec = get_record(url)
    for identifier in jrec['ids']:
        if identifier['schema'] == 'ORCID':
            return identifier['value']
    return None
