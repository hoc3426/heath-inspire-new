#!/usr/bin/python
'''
Check that we have an accepted manuscript.
All DOIs are lower-cased for the purpose of matching.
'''

import logging
import re
from collections import Counter

from inspire_api import get_result, get_result_ids
from osti_accepteds import retrieve_accepteds
from osti_fermilab_accepted_report_dois import DOIS

DIVISIONS = ['A', '(AD|APC)', 'AE', 'CD', 'CMS', 'DI', 'E', 'LBNF', 'ND',
             'PPD', 'T', 'TD']
DIVISIONS = ['(AD|APC)', 'CD', 'CCD', 'DI', 'ESH', 'FESS', 'LBNF', 'ND',
             '(A|AE|CMS|E|PPD|T)', 'PIP2', 'QIS', 'SCD', 'TD', 'WDRS', 'V']

JOURNALS = []
LOGFILE = __file__
LOGFILE = re.sub(r'.*\/', 'tmp_', LOGFILE)
LOGFILE = re.sub('.py', '.log', LOGFILE)
logging.basicConfig(filename=LOGFILE, filemode='w',
                    format='%(message)s',
                    level=logging.INFO)

def get_doi_report_dict():
    '''Create a dictionary keyed on the DOIs'''

    doi_report_dict = {}
    accepteds = retrieve_accepteds()
    for osti in accepteds:
        for doi in accepteds[osti][2]:
            doi_report_dict[doi.lower()] = accepteds[osti][1]
    return doi_report_dict

DOI_REPORT_DICT = get_doi_report_dict()

def get_doi_prefix(doi):
    '''Use the DOI prefix as a proxy for journals'''

    JOURNALS.append(re.sub(r'\/.*', '', doi))

def get_fermilab_report(recid):
    '''Get the Fermilab report number.'''

    accepted = False
    fermilab_report = None

    result = get_result(search=f'recid:{recid}',
                        fields='report_numbers')
    try:
        reports = result[0]['metadata']['report_numbers']
    except KeyError:
        return (fermilab_report, accepted)
    for report in reports:
        report = report['value'].upper()
        if report.startswith('FERMILAB'):
            fermilab_report = report
        elif report == 'OSTI_ACCEPTED':
            accepted = True
    return (fermilab_report, accepted)


def get_recid_from_doi(doi):
    '''Find if we have a DOI.'''

    recid = get_result_ids(f'doi:{doi}')
    if recid == []:
        recid = get_result_ids(f'doi:{doi}+_collection=Fermilab')
    if len(recid) == 1:
        return recid[0]
    return None

def calculate_output(numerator, denominator):
    '''Calculates a percentage.'''

    fraction = str(numerator) + '/' + str(denominator)
    if denominator:
        percentage = 100*float(numerator)/float(denominator)
        flag = ' '
        if percentage < 85:
            flag = '*'
        output = '{0:>8s} ({1:>6.2f}%){2}'.format(fraction, percentage, flag)
    else:
        output = '{0:>8s} ({1:>7}) '.format(fraction, 'N/A')
    return output

def examine(doi):
    '''
    Checks the status of a record to see if it has a DOI
    and if it does, if it has a Fermilab report number.
    '''

    if doi in DOI_REPORT_DICT:
        return (True, DOI_REPORT_DICT[doi])
    recid = get_recid_from_doi(doi)
    if not recid:
        logging.info('Need DOI')
        logging.info('  https://doi.org/%s', doi)
        return (False, None)
    get_doi_prefix(doi)
    report, accepted = get_fermilab_report(recid)
    if not report:
        logging.info('* Need report')
        logging.info('  https://old.inspirehep.net/record/%s', recid)
        return (False, None)
    if re.match(r'.*\d$', report):
        logging.info('* No division or section %s', report)
        logging.info('  https://old.inspirehep.net/record/%s', recid)
    if accepted:
        return (True, report)
    #if check_already_sent(recid):
    #    return (True, report)
    logging.info('Need accepted version %s', report)
    logging.info('  https://old.inspirehep.net/record/%s', recid)
    return (False, report)

def process_dois(dois):
    '''Go through a list of DOIs and check our holdings.'''

    report_numbers_good = set()
    report_numbers_bad = set()
    for doi in dois:
        (sent_to_osti, report) = examine(doi.lower())
        if not report:
            continue
        if sent_to_osti:
            report_numbers_good.add(report)
        else:
            report_numbers_bad.add(report)
    return (report_numbers_good, report_numbers_bad)


def main():
    '''Examines compliance by fiscal year.'''

    for year in sorted(DOIS):
        logging.info(year)
        (report_numbers_good, report_numbers_bad) = process_dois(DOIS[year])
        print('Fiscal Year:', year)
        print('Sent to OSTI:', calculate_output(len(report_numbers_good),
                                                len(DOIS[year])))
        for division in DIVISIONS:
            division_good = division_bad = 0
            for report in report_numbers_good:
                if re.match(r'.*-' +  division + r'\b.*', report):
                    division_good += 1
            for report in report_numbers_bad:
                if re.match(r'.*-' +  division + r'\b.*', report):
                    division_bad += 1
            print("  {0:25s} {1:>20s}".format(division,
                  calculate_output(division_good,
                                   division_good + division_bad)))
            #print "  {0:25s} {1:>20s}".format(division,
            #      calculate_output(len(report_numbers_good)-division_good,
            #                       len(DOIS[year])-(division_good +
            #                           division_bad)))

        labwide_good = labwide_bad = 0
        labwide_good_reports = []
        for report in report_numbers_good:
            if re.match(r'.*-\d+$', report):
                labwide_good += 1
                labwide_good_reports.append(report)
        for report in report_numbers_bad:
            if re.match(r'.*-\d+$', report):
                labwide_bad += 1
        print("  {0:25s} {1:>20s}".format('No div.',
              calculate_output(labwide_good,
                               labwide_good + labwide_bad)))
        #print labwide_good_reports

    JOURNALS.sort()
    for key in Counter(JOURNALS).most_common():
        logging.info('{0:30s} {1:>4d}'.format(key[0], key[1]))

    print(LOGFILE)


if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        print('Exiting')
