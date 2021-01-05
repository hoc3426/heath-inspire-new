"""Script to get the full-text for requested Fermilab report numbers."""

from fermilab_eprint_report_input import REPORTS
from inspire_api import get_result

def main(reports):
    """Print the Fermilab report number on a PDF stored at INSPIRE"""

    for report in reports:
        done = False
        fields = 'arxiv_eprints,documents,urls'
        result = get_result('find r ' + report, fields)
        #print(result)
        try:
            urls = result[0]['metadata']['urls']
        except (IndexError, KeyError):
            continue
        for url in urls:
            try:
                url_desc = url['description']
            except KeyError:
                print('Problem with:', report)
                print(url)
                quit()
            if url_desc.lower().startswith('fermilab library'):
                print(report, 'DONE')
                done = True
                break
        if done:
            continue
        try:
            eprint = result[0]['metadata']['arxiv_eprints'][0]['value']
            print(report, eprint)
            continue
        except (IndexError, KeyError):
            pass
        try:
            url = result[0]['metadata']['documents'][0]['url']
            print(report, url)
        except (IndexError, KeyError):
            continue

if __name__ == '__main__':
    try:
        main(REPORTS)
    except KeyboardInterrupt:
        print('Exiting')
