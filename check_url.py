'''Checks to see if a URL returns well-formed PDF and accepted manuscripts'''

import PyPDF2
import requests

TMP_PDF_FILE = '/tmp/file.pdf'
ACCEPTED_DESC = ['article from scoap3',
                 'fermilab accepted manuscript',
                 'fulltext from publisher',
                 'open access fulltext']
FERMILAB_DESC = 'fermilab library server'

def get_pdf_from_url(url):
    '''Checks a URL to return a well-formed PDF or returns None'''

    try:
        response = requests.get(url)
    except requests.exceptions.RequestException as err:
        print(f'url: {url} could not be reached: {err}')
        return None
    if response.status_code != 200:
        print(f'url: {url} does not work')
        return None
    if response.headers['content-type'] != 'application/pdf':
        print(f'url: {url} does not return a pdf file')
        return None
    with open(TMP_PDF_FILE, 'wb') as fhandle:
        fhandle.write(response.content)
    try:
        PyPDF2.PdfFileReader(open(TMP_PDF_FILE, 'rb'))
        return TMP_PDF_FILE
    except (PyPDF2.utils.PdfReadError, TypeError):
        print(f'url: {url} does not return a valid pdf file')
        return None

def get_url_check_accepted(jrec):
    '''Get the url from a record and check if the PDF is accepted'''

    accepted = False
    url = None
    urls = []
    try:
        urls += jrec['urls']
    except (KeyError, TypeError):
        pass
    try:
        urls += jrec['documents']
    except (KeyError, TypeError):
        pass
    for url_dict in urls:
        try:
            description = url_dict['description'].lower()
        except KeyError:
            continue
        try:
            url_value = url_dict['value']
        except KeyError:
            try:
                url_value = url_dict['url']
            except KeyError:
                continue
        if description in ACCEPTED_DESC:
            return [url_value, True]
        if description.startswith(FERMILAB_DESC):
            url = url_value
    return [url, accepted]
