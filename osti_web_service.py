'''
Script to push information on Fermilab publications
to OSTI using the webservice AN241.1.
'''

import xml.etree.ElementTree as ET
from xml.dom import minidom

import argparse
import re
from html import escape
from os import path
import datetime
import shutil
import sys

from authors import get_orcid_from_author
from inspire_api import get_result, get_result_ids
from check_url import get_url_check_accepted, get_pdf_from_url
from osti_accepteds import check_in_accepteds,\
                           retrieve_accepteds, store_accepteds
from osti_web_service_constants import TYPE_DICT, \
        DOE_SUBJECT_CATEGORIES_DICT, \
        DOE_FERMILAB_DICT, DOE_AFF_DICT, \
        INSPIRE_AFF_DICT
from osti_web_service_search_constants import SEARCH_DEFAULT, SEARCH_DATE, \
                                              SEARCH_ACCEPTED, SEARCH_ACCEPTED_END, \
                                              SEARCH_FNAL, SEARCH_OSTI

TEST = True
TEST = False
LOGFILE = 'osti_web_service.log'
VERBOSE = True
VERBOSE = False
ENDING_COUNTER = 20

def create_osti_id_pdf(jrec=None, recid=None, osti_id=None,
                       doi=None, reports=None):
    '''
    Places a PDF named after the OSTI id in a location that
    can be pushed to OSTI.
    If the pdf is not of an excepted paper it skips this.
    '''

    if jrec and recid is None:
        recid = jrec['control_number']
    if recid is None or osti_id is None or doi is None or reports is None:
        return None
    accepteds = retrieve_accepteds()
    if int(osti_id) in accepteds:
        print(f'Already sent accepted PDF: recid={recid}, osti_id={osti_id}')
        return None
    url, accepted = get_url_check_accepted(jrec)
    if not accepted:
        return None
    new_pdf = f'osti_pdf/{osti_id}.pdf'
    if not path.exists(new_pdf):
        pdf = get_pdf_from_url(url)
        if not pdf:
            print(f'https://inspirehep.net/literature/{recid}')
            return None
        try:
            shutil.move(pdf, new_pdf)
        except shutil.Error as err:
            print(f'Problem creating {new_pdf} from {pdf}: {err}')
            return None
    if osti_id.isdigit():
        accepteds[int(osti_id)] = [recid, reports, set([doi])]
        print(osti_id, accepteds[int(osti_id)])
    else:
        print(f'Bad OSTI ID {osti_id}')
        sys.exit()
    if not TEST:
        store_accepteds(accepteds)
    return True

def get_language(jrec):
    ''' Find the langauge of the work. '''

    try:
        return jrec['languages'][0]
    except KeyError:
        return 'English'

def get_osti_id(jrec):
    ''' Find the osti_id from an INSPIRE record '''

    try:
        identifiers = jrec['external_system_identifiers']
    except (KeyError, TypeError):
        return None
    for identifier in identifiers:
        if identifier['schema'].lower() == 'osti':
            return identifier['value']
    return None

def check_already_sent(jrec):
    '''Looks to see if we've already sent the AM to OSTI.'''

    osti_id = get_osti_id(jrec)
    if not osti_id:
        return False
    if check_in_accepteds(osti_id):
        return True
    return False

def get_title(jrec):
    '''Get title with in xml compliant form.'''
    try:
        title = jrec['titles'][0]['title']
        title = escape(title)
        return title
    except IndexError:
        print('Problem with title on', jrec['control_number'])
        return None

def get_pubnote(jrec):
    '''Gets publication information'''
    try:
        journal = jrec['publication_info'][0]['journal_title']
    except KeyError:
        journal = None
    try:
        volume = jrec['publication_info'][0]['journal_volume']
    except KeyError:
        volume = None
    try:
        issue = jrec['publication_info'][0]['journal_issue']
    except KeyError:
        issue = None
    try:
        pages = jrec['publication_info'][0]['artid']
    except KeyError:
        try:
            pages = jrec['publication_info'][0]['page_start']
        except KeyError:
            pages = None
    try:
        doi = jrec['dois'][0]['value']
    except KeyError:
        doi = None
    return [journal, volume, issue, pages, doi]

def get_conference(jrec_hep):
    ''' Get conference information '''

    try:
        cnum = jrec_hep['metadata']['publication_info'][0]['cnum']
    except KeyError:
        return None
    search = 'cnum:' + cnum
    jrec_confs = get_result(search, fields=None)
    if len(jrec_confs) != 1:
        return None
    jrec_conf = jrec_confs[0]
    try:
        conference_note = jrec_conf['metadata']['titles'][0]['title']
    except KeyError:
        conference_note = ''
    try:
        for item in jrec_conf['metadata']['address']:
            if 'cities' in item:
                conference_note += ', ' + item['cities'][0]
            if 'state' in item:
                conference_note += ', ' + item['state']
            if 'country_code' in item:
                conference_note += ', ' + item['country_code']
    except KeyError:
        pass
    try:
        date = jrec_conf['metadata']['opening_date']
        #date = get_fieldvalues(recid, "111__x")[0]
        date_object = datetime.datetime.strptime(date, '%Y-%m-%d')
        date = date_object.strftime('%m/%d')
        conference_note += ', ' + date
    except KeyError:
        pass
    try:
        date = jrec_conf['metadata']['closing_date']
        date_object = datetime.datetime.strptime(date, '%Y-%m-%d')
        date = date_object.strftime('%m/%d/%Y')
        conference_note += '-' + date
    except KeyError:
        pass
    if conference_note:
        return conference_note
    return None

def get_author_details(jrec, authors):
    '''Get authors broken out as individuals'''

    try:
        paper_authors = jrec['authors']
    except KeyError:
        return None
    for item in paper_authors:
        authors_detail = ET.SubElement(authors, 'authors_detail')
        author = None
        last_name = None
        first_name = None
        middle_name = None
        affiliation = None
        email = None
        orcid = None
        try:
            author = item['full_name']
            try:
                matchobj = re.match(r'(.*)\, (.*)\, (.*)', author)
                last_name = matchobj.group(1)
                fore_name = matchobj.group(2)
                title = matchobj.group(3)
                fore_name = fore_name + ', ' + title
            except AttributeError:
                last_name = re.sub(r'\,.*', '', author)
                fore_name = re.sub(r'.*\, ', '', author)
            if re.search(r' ', fore_name):
                first_name = re.sub(r' .*', '', fore_name)
                middle_name = re.sub(r'.* ', '', fore_name)
            elif re.search(r'^\w\.\w\.', fore_name):
                first_name = re.sub(r'^(\w\.).*', r'\1', fore_name)
                middle_name = re.sub(r'^\w\.', '', fore_name)
            else:
                first_name = fore_name
        except KeyError:
            pass
        try:
            affiliation = '; '.join([x['value'] for x in item['affiliations']])
        except KeyError:
            pass
        try:
            email = item['emails'][0]
            email = email.replace('email:', '')
        except KeyError:
            pass
        try:
            for id_num in item['ids']:
                if id_num['schema'] == 'ORCID':
                    orcid = re.sub(r'ORCID:', '', id_num['value'])
        except KeyError:
            pass
        if orcid is None:
            orcid = get_orcid_from_author(item)
        ET.SubElement(authors_detail, 'first_name').text = first_name
        ET.SubElement(authors_detail, 'middle_name').text = middle_name
        ET.SubElement(authors_detail, 'last_name').text = last_name
        ET.SubElement(authors_detail, 'affiliation').text = affiliation
        ET.SubElement(authors_detail, 'private_email').text = email
        ET.SubElement(authors_detail, 'orcid_id').text = orcid

def get_corporate_author(jrec):
    '''Check to see if there is a corporte author and return it.'''

    try:
        #author_list = jrec['corporate_author']
        authors = []
        author_dict_list = jrec['record_affiliations']
        for author_dict in author_dict_list:
            authors.append(author_dict['value'])
        return '; '.join(authors)

    except KeyError:
        return None

def get_author_first(jrec):
    '''Get authors as a long string, truncate at 10.'''
    try:
        return jrec['authors'][0]['full_name'] + '; et al.'
    except KeyError:
        return None

def get_author_number(jrec):
    '''Gets number of authors.'''
    try:
        return len(jrec['authors'])
    except KeyError:
        return 0

def get_collaborations(jrec):
    '''Get the collaboration information'''
    try:
        collaborations = [x['value'] for x in
                          jrec['collaborations']]
        return '; '.join(collaborations)
    except KeyError:
        return None

def get_abstract(jrec):
    '''Get abstract if it exists.'''
    try:
        abstract = jrec['abstracts'][0]['value']
        if len(abstract) > 4990:
            abstract = abstract[:4990] + '...'
        return abstract
    except KeyError:
        return None

def get_report_hidden(jrec):

    hidden = False
    try:
        reports = jrec['report_numbers']
    except KeyError:
        print(jrec)
        print('No report number')
        quit()
    for report in jrec['report_numbers']:
        if 'hidden' in report and report['value'].startswith('FERMILAB'):
            if report['hidden']:
                hidden = True
    return hidden

def get_reports(jrec):
    '''Get reports as a long string.'''

    eprint = get_eprint(jrec)
    try:
        reports = [x['value'] for x in jrec['report_numbers']]
        report = '; '.join(r for r in reports)
        if eprint:
            report += f'; arXiv:{eprint}'
        return report
    except KeyError:
        return ''

def get_product_type(jrec):
    '''Get product type in OSTI format.'''
    type_dict = TYPE_DICT
    product_type = '??'
    report_string = get_reports(jrec)
    for key in type_dict:
        pattern = 'FERMILAB-' + key
        if re.search(pattern, report_string):
            product_type = type_dict[key]
    if VERBOSE:
        print(product_type)
    return product_type

def get_subject_categories(jrec):
    '''Convert INSPIRE subject codes to OSTI codes.'''

    try:
        categories = jrec['inspire_categories']
    except KeyError:
        return None
    osti_categories = []
    for category in categories:
        for key in DOE_SUBJECT_CATEGORIES_DICT:
            if re.search(key, category['term'].lower()):
                osti_categories.append(DOE_SUBJECT_CATEGORIES_DICT[key])
    return '; '.join(c for c in set(osti_categories))

def get_affiliations(jrec, long_flag):
    '''Get affiliations using OSTI institution names.'''

    affiliations = set(['Fermilab'])
    paper_authors = None
    try:
        paper_authors = jrec['authors']
        for author in paper_authors:
            if not 'affiliations' in author:
                continue
            for affiliation in author['affiliations']:
                affiliations.add(affiliation['value'])
    except KeyError:
        pass
    doe_affs = []
    doe_affs_long = []
    for aff in affiliations:
        if aff in INSPIRE_AFF_DICT:
            doe_affs.append(INSPIRE_AFF_DICT[aff])
            doe_affs_long.append(DOE_AFF_DICT[INSPIRE_AFF_DICT[aff]])
    if long_flag:
        return '; '.join(doe_affs_long)
    return '; '.join(doe_affs)

def get_eprint(jrec):
    '''Get the eprint number'''

    try:
        return jrec['arxiv_eprints'][0]['value']
    except KeyError:
        return None

def get_date(jrec, product_type):
    '''Get date in format mm/dd/yyyy, yyyy or yyyy Month.'''
    try:
        date = jrec['imprints'][0]['date']
    except KeyError:
        try:
            date = jrec['preprint_date']
        except KeyError:
            try:
                date = jrec['thesis_info']['date']
            except KeyError:
                date = '1900'
    try:
        date_object = datetime.datetime.strptime(date, '%Y-%m-%d')
        date = date_object.strftime('%m/%d/%Y')
    except ValueError:
        try:
            date_object = datetime.datetime.strptime(date, '%Y-%m')
            date = date_object.strftime('%Y %B')
            if product_type in ['TR', 'TD', 'JA']:
                date = date_object.strftime('%m/01/%Y')
        except ValueError:
            if product_type in ['TR', 'TD', 'JA']:
                date = '01/01/' + str(date)
    return date

def prettify(elem):
    '''Return a pretty-printed XML string for the Element.'''

    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

#def create_xml(recid, records):
def create_xml(jrec, records):
    '''
    Creates xml entry for a recid and feeds it to list of records.
    Tests to see if all the necessary information is present.
    If an accepted version has already been submitted, returns None.
    '''

    url, accepted = get_url_check_accepted(jrec)
    if VERBOSE:
        print(url, accepted)
    if url is None:
        if get_report_hidden(jrec):
            eprint = get_eprint(jrec)
            if eprint:
                url = f'https://arxiv.org/pdf/{eprint}.pdf'
        else:
            return None
    osti_id = get_osti_id(jrec)
    if check_in_accepteds(osti_id):
        return None
    recid = jrec['control_number']
    product_type = get_product_type(jrec)
    if accepted:
        product_type = 'JA'
    ##journal_info = get_pubnote(jrec)
    ##if product_type == 'JA' and journal_info[0] is None:
    ##    return None
    #Begin building record
    record = ET.SubElement(records, 'record')
    if osti_id:
        ET.SubElement(record, 'osti_id').text = osti_id
        dict_osti_id = {'osti_id':osti_id}
        ET.SubElement(record, 'revdata', dict_osti_id)
        ET.SubElement(record, 'revprod', dict_osti_id)
    else:
        ET.SubElement(record, 'new')
    ET.SubElement(record, 'site_input_code').text = \
        DOE_FERMILAB_DICT['site_input_code']
    if product_type == 'JA':
        if accepted:
            ET.SubElement(record, 'journal_type').text = 'AM'
            #print 'Accepted Manuscript', recid, osti_id
            #create_osti_id_pdf(jrec, recid, osti_id)
        else:
            ET.SubElement(record, 'journal_type').text = 'FT'
    if product_type.startswith(r'CO.'):
        product_subtype = re.sub(r'.*\.', '', product_type)
        product_type = re.sub(r'\..*', '', product_type)
        ET.SubElement(record, 'product_type',
                      product_subtype=product_subtype).text = \
                     product_type
    else:
        ET.SubElement(record, 'product_type').text = product_type
    access_limitation = ET.SubElement(record, 'access_limitation')
    ET.SubElement(access_limitation, 'unl')
    if not accepted:
        ET.SubElement(record, 'site_url').text = url
    ET.SubElement(record, 'title').text = get_title(jrec)
    collaborations = get_collaborations(jrec)
    author_number = get_author_number(jrec)

    corporate_author = get_corporate_author(jrec)
    if corporate_author:
        author = ET.SubElement(record, 'author')
        author.text = corporate_author

    elif author_number > 20:
        author = ET.SubElement(record, 'author')
        author_first = get_author_first(jrec)
        if author_first:
            author.text = get_author_first(jrec)
    else:
        authors = ET.SubElement(record, 'authors')
        get_author_details(jrec, authors)
    ET.SubElement(record, 'contributor_organizations').text = \
        collaborations
    reports = get_reports(jrec)
    ET.SubElement(record, 'report_nos').text = reports
    for key in DOE_FERMILAB_DICT:
        ET.SubElement(record, key).text = DOE_FERMILAB_DICT[key]
    ET.SubElement(record, 'description').text = get_abstract(jrec)
    ET.SubElement(record, 'originating_research_org').text = \
        get_affiliations(jrec, True)
    journal_info = get_pubnote(jrec)
    if product_type == 'JA' and journal_info[0] is None:
        journal_elements = ['journal_name']
        journal_info = ['TBD']
    else:
        journal_elements = ['journal_name', 'journal_volume', 'journal_issue',
                            'product_size', 'doi']
    i_count = 0
    for journal_element in journal_elements:
        ET.SubElement(record, journal_element).text = journal_info[i_count]
        i_count += 1
    try:
        doi = journal_info[4]
    except IndexError:
        doi = None
    if product_type == 'CO':
        ET.SubElement(record, 'conference_information').text = \
        get_conference(jrec)
    ET.SubElement(record, 'other_identifying_nos').text = \
        f'oai:inspirehep.net:{recid}'
    ET.SubElement(record, 'publication_date').text = \
        get_date(jrec, product_type)
    ET.SubElement(record, 'language').text = \
        get_language(jrec)
    ET.SubElement(record, 'subject_category_code').text = \
        get_subject_categories(jrec)
    ET.SubElement(record, 'released_date').text = \
        datetime.datetime.now().strftime('%m/%d/%Y')
          #CHICAGO_TIMEZONE.fromutc(datetime.datetime.utcnow()).\
          #strftime('%m/%d/%Y')
    if accepted:
        create_osti_id_pdf(jrec, recid, osti_id, doi, reports)
    return True

def main(result):
    '''Generate OSTI posting from a recid or an INSPIRE search.'''

    counter = 0
    if not result:
        print("No, that search did not work")
        return None
    filename = 'tmp_' + __file__
    filename = re.sub(r'.*\/', '', filename)
    filename = re.sub('.py', '.out', filename)
    print(filename)
    output = open(filename, 'w')

    records = ET.Element('records')
    for jrec in result:
        if counter > ENDING_COUNTER:
            break
        if check_already_sent(jrec):
            if VERBOSE:
                print("Already sent", jrec['control_number'])
            continue
        record_test = create_xml(jrec, records)
        if record_test:
            counter += 1
    if TEST:
        print(prettify(records))
    else:
        #output.write(XML_PREAMBLE)
        output.write(prettify(records))
    output.close()
    print("Number of records:", counter)

def find_result(search_input=None):
    ''' Finds records to send email to. '''

    if not search_input:
        search_input = input('Your search? ').lower()
        if len(search_input) > 3:
            search = f'{search_input} {SEARCH_FNAL}'
            search += f' {SEARCH_DATE} -{SEARCH_OSTI}'
        else:
            print('Badly formed search.')
            return None
    else:
        search = search_input
    print(search)
    result = get_result(search)
    if VERBOSE:
        print(len(result))
    if len(result) > 0:
        log = open(LOGFILE, 'a')
        date_time_stamp = \
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        date_time_stamp = date_time_stamp + ' ' + search + ' : '\
                    + str(len(result)) + '\n'
        log.write(date_time_stamp)
        log.close()
        return result
    print('No result found')
    return None

def get_new_accepteds():
    '''Find the new accepted PDFs'''

    recid_list = []
    for search in SEARCH_ACCEPTED:
        search += SEARCH_ACCEPTED_END
        recid_list.extend(get_result_ids(search))
    result = set(recid_list)
    sent = retrieve_accepteds()
    sent_recids = set()
    for osti in sent:
        sent_recids.add(str(sent[osti][0]))
    new_accepteds_recids = list(result - sent_recids)
    if len(new_accepteds_recids) == 0:
        return None
    jrec_new_accepteds = []
    for recid in new_accepteds_recids[:20]:
        jrec_new_accepteds.extend(get_result(recid))
    return jrec_new_accepteds

if __name__ == '__main__':

    RESULT = None
    SEARCH = SEARCH_DEFAULT
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--accepted',
                        help='Look for new accepted manuscripts',
                        action='store_true')
    parser.add_argument('-i', '--include',
                        help='Include records that already have an OSTI ID',
                        action='store_true')
    parser.add_argument('-r', '--record', type=int,
                        help='Run on a single record')
    parser.add_argument('-s', '--search',
                        help='Run on this search',
                        action='store_true')
    parser.add_argument('-t', '--test',
                        help='Run in test mode',
                        action='store_true')
    parser.add_argument('-v', '--verbose',
                        help='Run in verbose mode',
                        action='store_true')
    args = parser.parse_args()
    if args.accepted:
        RESULT = get_new_accepteds()
    if args.include:
        pass
    if args.record:
        SEARCH = f'recid:{args.record}'
    if args.search:
        SEARCH = None
    if args.test:
        TEST = True
    if args.verbose:
        VERBOSE = True
    if not RESULT:
        RESULT = find_result(SEARCH)
    try:
        main(RESULT)
    except KeyboardInterrupt:
        print('Exiting')
