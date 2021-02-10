#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""
Script for adding OSTI IDs to INSPIRE records after using OSTI Web Service.
"""

import re
import xml.etree.ElementTree as ET

from inspire_api import get_result, get_result_ids
from osti_web_service import create_osti_id_pdf, get_pubnote
from osti_fermilab_accepted_report import get_fermilab_report

TEST = False
#TEST = True
DOCUMENT = 'tmp_osti.out'
VERBOSE = False
VERBOSE = True

if TEST:
    DOCUMENT = 'tmp_osti_test.out'

RECIDS = []


def print_rec(osti_id, recid):
    '''Create an xml record to upload'''

    return f'''<record>
  <controlfield tag="001">{recid}</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="a">{osti_id}</subfield>
    <subfield code="9">OSTI</subfield>
  </datafield>
</record>'''

def create_xml(osti_id, recid):
    """
    The function checks if the OSTI ID should be added to INSPIRE.
    If so, it builds up that information.
    """

    osti_id = str(osti_id)
    recid = str(recid)
    recid = recid.replace('oai:inspirehep.net:', '')
    search = f'_collections:Fermilab recid:{recid}'
    result = get_result(search)
    if len(result) == 0:
        print(f'No such INSPIRE Fermilab record {recid}')
        return None
    jrec = result[0]
    report = get_fermilab_report(recid)[0]
    doi = get_pubnote(jrec)[4]
    create_osti_id_pdf(jrec, recid, osti_id, doi, report)
    search = '_collections:Fermilab '
    search += f'external_system_identifiers.value:{osti_id} '
    search += 'external_system_identifiers.schema:osti'
    result_osti = get_result_ids(search)
    if result_osti == recid:
        return None
    if len(result_osti) == 1:
        print(f'OSTI ID {osti_id} already on {result_osti[0]}')
        return None
    search = f'recid:{recid} -external_system_identifiers.schema:osti'
    if TEST:
        print(search)
    result = get_result_ids(search)
    if len(result) != 1:
        print(f'Problem with {recid} {osti_id}')
        print(f'  {search} {result}')
        return False
    if TEST:
        print(result)
    return print_rec(osti_id, recid)


def main():
    """
    Takes the output from an OSTI web push and appends the
    OSTI IDs to the INSPIRE records.
    """

    filename = 'tmp_' + __file__
    filename = re.sub('.py', '_append.out', filename)
    output = open(filename, 'w')
    output.write('<collection>')
    tree = ET.parse(DOCUMENT)
    root = tree.getroot()
    for record in root.findall('record'):
        print(record.tag)
        osti_id = record.find('osti_id').text
        if VERBOSE:
            print(osti_id)
        if osti_id == '0':
            continue
        recid = record.find('other_identifying_nos').text
        if VERBOSE:
            print(recid)
        record_update = create_xml(osti_id, recid)
        if record_update:
            try:
                if TEST:
                    print(record_update)
                else:
                    output.write(record_update)
            except IOError:
                print(f'CANNOT print record {record.attrib}')
    output.write('</collection>')
    output.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Exiting')
