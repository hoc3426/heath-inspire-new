"""Script to get the full-text for requested Fermilab report numbers."""

from fermilab_eprint_report_input import REPORTS
from inspire_api import get_result

def main(reports):
    """Print the Fermilab report number on a PDF stored at INSPIRE"""

    for report in reports:
        result = get_result('find r ' + report, 'arxiv_eprints,documents')
        eprint = result[0]['metadata']['arxiv_eprints'][0]['value']
        url = result[0]['metadata']['documents'][0]['url']
        print(report, eprint, url)

if __name__ == '__main__':
    try:
        main(REPORTS)
    except KeyboardInterrupt:
        print('Exiting')
