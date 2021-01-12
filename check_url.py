'''Checks to see if a URL returns well-formed PDF'''

import PyPDF2
import requests

def check_url(url):
    '''Checks to see if a URL returns well-formed PDF'''

    try:
        response = requests.get(url)
    except requests.exceptions.RequestException as err:
        print(f'url: {url} could not be reached')
        return None
    if response.status_code != 200:
        print(f'url: {url} is not valid')
        return None
    if response.headers['content-type'] != 'application/pdf':
        print(f'url: {url} does not return a pdf file')
        return None
    tmp_pdf_file = '/tmp/file.pdf'
    with open(tmp_pdf_file, 'wb') as fhandle:
        fhandle.write(response.content)
    try:
        PyPDF2.PdfFileReader(open(tmp_pdf_file, 'rb'))
        return True
    except (PyPDF2.utils.PdfReadError, TypeError):
        print(f'url: {url} does not return a valid pdf file')
        return None
