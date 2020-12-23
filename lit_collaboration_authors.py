# -*- coding: utf-8 -*-

"""
A system to extract collaboration author lists from tex files or ieee.
"""

import json
import getopt
import os
import re
import sys
import tarfile
import time

import arxiv
import requests
from pylatexenc.latex2text import LatexNodes2Text
from unidecode import unidecode

from inspire_api import get_result_ids

EMAIL_REGEX = re.compile(r"^[\w\-\.\'\+]+@[\w\-\.]+\.\w{2,4}$")
ORCID_REGEX = re.compile(r'^0000-\d{4}-\d{4}-\d{3}[\dX]$')
EPRINT_REGEX = re.compile(r'^(\d{4}\.\d{4}\d?|[a-z]+\-?[a-z]+\d{7})$')
DOI_REGEX = re.compile(r'10\.\d{4}\d?\/\S+$')
INSPIRE_REGEX = re.compile(r'^INSPIRE-\d{8}$')
AFFILIATIONS_DONE = {}

DIRECTORY = '/tmp/'

def download_source(eprint='2012.06888', bib=False, dat=False):
    """Download a tar file from arXiv and choose the right file."""

    filename = eprint.replace('/', '-')
    paper = arxiv.query(id_list=[eprint])[0]
    paper = arxiv.download(paper, prefer_source_tarfile=True)
    this_tarfile = tarfile.open(paper, 'r')
    tarfiles = {}
    file_count = 0
    for this_file in this_tarfile.getnames():
        file_type_regex = re.compile(r'^.*(tex|xml|txt)$')
        if bib:
            file_type_regex = re.compile(r'^.*(tex|xml|txt|bib|bbl|inc)$')
        if dat:
            file_type_regex = re.compile(r'^.*(tex|xml|txt|dat)$')
        if file_type_regex.match(this_file):
            file_count += 1
            tarfiles[file_count] = this_file
            print(file_count, tarfiles[file_count])
    if file_count == 1:
        file_choice = file_count
    else:
        file_choice = input('Choose a file: ')
        file_choice = int(file_choice)
    source_file = this_tarfile.extractfile(tarfiles[file_choice])
    file_type = re.match(r'.*(\w{3})$', tarfiles[file_choice]).group(1)
    output = open(filename + '.' + file_type, 'wb')
    output.write(source_file.read())
    output.close()
    os.unlink(paper)
    return file_type

def author_first_last(author):
    """Determines the components of the author's name.."""

    #Handle ways for 'q'
    qname = re.search(r'\s*\\\\begin{CJK\*}{UTF8}{gkai}\((.*)\)\\\\end{CJK\*}',
                      author, re.U)
    if not qname:
        qname = re.search(r'\(chname\{(.*)\}\)', author, re.U)
    if qname:
        author = author.replace(qname.group(0), u'')
        qname = ':' + qname.group(1)
    else:
        qname = ''
    if re.search(r',', author):
        author = re.sub(r'\,\s*', ', ', author)
        return author + qname
    if re.match(r'^Tatjana Agatonovic Jovin$', author):
        return 'Agatonovic Jovin, Tatjana'
    if re.match(r'^Ivanka Bozovic Jelisavcic$', author):
        return 'Bozovic Jelisavcic, Ivanka'
    if re.match(r'^Enrique Calvo Alamillo$', author):
        return 'Calvo Alamillo, Enrique'
    if re.match(r'^Ziad El Bitar$', author):
        return 'El Bitar, Ziad'
    if re.match(r'^Hector García Cabrera$', author):
        return 'García Cabrera, Hector'
    if re.match(r'^Amir Noori Shirazi$', author):
        return 'Noori Shirazi, Amir'
    if re.match(r'^Maria Soledad Robles Manzano$', author):
        return 'Robles Manzano, Maria Soledad'
    if re.match(r'^Antonio Verdugo de Osa$', author):
        return 'Verdugo de Osa, Antonio'
    #Anything ending in a period is the firstname block
    if re.search(r'\. [^\.]+$', author, re.U):
        return re.sub(r'(.*\.) ([^\.]+)', r'\2, \1', author, re.U) + \
               qname
    #Anything with only two parts
    if re.search(r'^\S+ \S+$', author, re.U):
        return re.sub(r'(.*) (.*)', r'\2, \1', author, re.U) + qname
    #Anything starting with a lower-case letter, e.g. Oscar de la Hoya
    pattern = re.compile(r' (\w+)', re.U)
    for last_guess in re.findall(pattern, author):
        firstname = False
        if last_guess in ['Da', 'De', 'Del', 'Della', 'Van', 'Von']:
            firstname = re.sub(last_guess + u'.*', '', author)
        elif last_guess[0].lower() == last_guess[0]:
            firstname = re.sub(last_guess + u'.*', '', author)
        if firstname:
            return author.replace(firstname, '') + ',' + firstname + qname
    match = re.match('(.*) (.*)', author, re.U)
    if match:
        return match.group(2) + u', ' + match.group(1) + qname
    return author + qname


def process_author_name(author):
    """Convert author to INSPIRE form."""


    #test for ALLCAPS
    author = author.replace('YYYY', '')
    if re.search(r'[A-Z][A-Z]', author):
        author_uplow = ''
        for part in author.split(' '):
            if part.upper() == part and not re.match(r'I[IV]+', part):
                part = part.title()
            author_uplow += ' ' + part
        author = author_uplow
    author = author.replace('Inspire', 'INSPIRE')

    #print 'INPUT = ', author
    author = author.replace(r'\.', r'xxxx')
    author = author.replace(r'.', '. ')
    author = author.replace(r'xxxx', r'\.')
    author = re.sub('[ ]+', ' ', author)
    author = re.sub(r'\\(cor|corauth|fn)ref\{\w+\}', r'', author)
    author = re.sub(r'\}?\\thanks\{\\?.*\}?', r'', author)
    author = author.replace(r'\,', r'~')
    author = author.replace(r'\~', r'xxxx')
    author = author.replace(r'~', r' ')
    author = author.replace(r'xxxx', r'\~')
    #print 'MIDWAY1 =', author
    #author = translate_latex2unicode(author)
    author = LatexNodes2Text().latex_to_text(author)
    author = author.replace('\\"i', 'ï')
    if '\\' in author and 'UTF8' not in author:
        print('Problem with', author)
        sys.exit()
    author = author.replace(',', ', ')
    author = author.replace('.', '. ')
    author = re.sub(r'\s+', ' ', author)
    author = re.sub(r'\s+$', '', author)
    author = re.sub(r'^\s+', '', author)
    #print 'MIDWAY2 =', author
    match_object_1 = re.match(r'^(.*\w) ([IVJr\.]{2,}$)', author)
    match_object_2 = re.match(r'(.*) (\(.*\))', author, re.U)
    if match_object_1 or match_object_2:
        if match_object_1:
            match_object = match_object_1
        elif match_object_2:
            match_object = match_object_2
        author = author_first_last(match_object.group(1)) + ', ' + \
                 match_object.group(2)
    else:
        author = author_first_last(author)
    author = author.replace(',', ', ')
    author = re.sub(r'\.\s+', '.', author)
    author = re.sub(r'\s+', ' ', author)
    author = re.sub(r'\s+$', '', author)
    author = re.sub(r'^\s+', '', author)



    #author = translate_latex2unicode(author)

    #print 'OUTPUT =', author
    return author

def get_recid(input_id):
    '''find recid based on eprint or doi'''

    if EPRINT_REGEX.match(input_id):
        search = 'find eprint ' + input_id
        if '/' in input_id or '.' in input_id:
            search = 'find eprint ' + input_id
        try:
            recid = get_result_ids(search)[0]
        except IndexError:
            print('Do not have eprint or recid', search)
            return None
    elif DOI_REGEX.match(input_id):
        try:
            search = 'find doi ' + input_id
            recid = get_result_ids(search)[0]
        except IndexError:
            print('Do not have doi', search)
            return None
    elif input_id.isdigit():
        recid = input_id
    else:
        recid = None
    return recid

#def create_xml(eprint=None, doi=None, author_dict=None):
def create_xml(author_dict=None):
    """Take in the author dictionary and write it out as xml."""

    aff_counter = 0
    new_aff_dict = {}
    new_author_dict = {}

    for key, value in author_dict.items():
        author = value[0].split(',')
        author.reverse()
        author = " ".join(author)
        if author in new_author_dict:
            author = author + '2'
        new_author_dict[author] = []
        for aff in value[1]:
            if aff not in new_aff_dict:
                aff_counter += 1
                new_aff_dict[aff] = aff_counter
            new_author_dict[author].append(new_aff_dict[aff])
        #print(author, new_author_dict[author], value[1])

    for author, affkeys in new_author_dict.items():
        print(author, ','.join(str(affkey) for affkey in affkeys))
    print('\n')
    for key, value in new_aff_dict.items():
        key = re.sub(r'\s+', ' ', key)
        print(value, LatexNodes2Text().latex_to_text(key))

    #print(new_author_dict)
    #print(new_aff_dict)

    record = {}
    #record_add_field(record, '001', controlfield_value=str(recid))
    #tag = '100__'
    #EMAIL_REGEX = re.compile(r"^[\w\-\.\'\+]+@[\w\-\.]+\.\w{2,4}$")
    #ORCID_REGEX = re.compile(r'^0000-\d{4}-\d{4}-\d{3}[\dX]$')
    #INSPIRE_REGEX = re.compile(r'^INSPIRE-\d{8}$')
    for key in author_dict:
        subfields = []
        author = author_dict[key][0]
        #print author_dict
        match_obj = re.search(ORCID_REGEX, author)
        if match_obj:
            orcid = match_obj.group(1)
            if not re.match(ORCID_REGEX, orcid):
                print('1 Problem with', orcid)
            if ('j', 'ORCID:' + orcid) not in subfields:
                subfields.append(('j', 'ORCID:' + orcid))
            author = author.replace(orcid, '')
            author = author.replace('[]', '')
        match_obj = re.search(r'(INSPIRE-\d{8})', author)
        if match_obj:
            inspire = match_obj.group(1)
            if not re.match(INSPIRE_REGEX, inspire):
                print('Problem with', inspire)
            subfields.append(('i', inspire))
            author = author.replace(inspire, '')
            author = author.replace('[]', '')
        if u':' in author:
            match_obj = re.match('(.*):(.*)', author, re.U)
            author = match_obj.group(1)
            subfields.append(('q', match_obj.group(2)))
        subfields.append(('a', author))

        for affiliation in author_dict[key][1]:
            affiliation = re.sub(r'\\affinfn{(.*)}{(.*)}', r'INFN \1 \2',
                                 affiliation)
            affiliation = re.sub(r'\\affuni{(.*)}{(.*)}', r'\1 University \2',
                                 affiliation)
            #affiliation = translate_latex2unicode(affiliation)
            affiliation = LatexNodes2Text().latex_to_text(affiliation)
            #affiliation = re.sub(r'(\w)\W*$', r'\1', affiliation)
            affiliation = re.sub(r'([\.\,]+)', r'\1 ', affiliation)
            affiliation = re.sub(r'\s+', ' ', affiliation)
            affiliation = re.sub(r'\s$', r'', affiliation)
            affiliation = re.sub(r'\s*also at[\:\s]*', r'',
                                 affiliation, re.IGNORECASE)
            affiliation = re.sub(r'\s*\\and$', r'', affiliation)

            if False and r"@" in affiliation and r"0000-" in affiliation:
                affiliation = affiliation.replace(';', ' ')
                affiliation = affiliation.replace(r'. ', r'.')
                email = re.search(r"(\S+\@\S+)", affiliation).group(1)
                orcid = re.search(r"(0000-\S+)", affiliation).group(1)
                if re.match(EMAIL_REGEX, email):
                    subfields.append(('m', 'email:' + email))
                else:
                    print('Email problem:', email)
                if re.match(ORCID_REGEX, orcid) and \
                   ('j', 'ORCID:' + orcid) not in subfields:
                    subfields.append(('j', 'ORCID:' + orcid))
                else:
                    print('ORCID problem:', orcid)
                continue
            if False and r"@" in affiliation:
                affiliation = affiliation.replace(r'. ', r'.')
                subfields.append(('m', affiliation))
                continue
            #elif re.match(r"^0000-0", affiliation):
            if False and re.search(r"0000-0", affiliation):
                #print 'XXX', affiliation
                for aff in affiliation.split():
                    aff = re.sub(r'[^\d^\-^X]', '', aff)
                    orcid = re.search(ORCID_REGEX, aff)
                    if orcid:
                        orcid = orcid.group(0)
                        if ('j', 'ORCID:' + orcid) not in subfields:
                            subfields.append(('j', 'ORCID:' + orcid))
                        affiliation = re.sub(orcid, '', affiliation)
                        affiliation = re.sub(r'\s+$', '', affiliation)

                        #print 'YYY', affiliation


                        #subfields.append(('v', affiliation))
                        #break
                if not orcid:
                    print('ORCID problem:', affiliation)
                #Removed this to process aff that contained ORCID
                #continue
            elif re.match(r"^INSPIRE-", affiliation):
                subfields.append(('i', affiliation))
                #Removed this to process aff that contained ORCID
                #continue

            affiliation = affiliation.replace('[]', '')
            if not affiliation:
                continue
            affiliation_key = re.sub(r'\W+', ' ', affiliation).upper()
            affiliation_key = re.sub(r'\s*(.+\S)\s*', r'\1', affiliation_key)
            try:
                for inst in AFFILIATIONS_DONE[affiliation_key]:
                    inst = re.sub(r'^\s+', '', inst)
                    if inst:
                        subfields.append(('u', inst))
            except KeyError:
                #inspire_affiliation = get_aff(unidecode(affiliation))
                inspire_affiliation = unidecode(affiliation)
                for inst in inspire_affiliation:
                    inst = re.sub(r'^\s+', '', inst)
                    if inst:
                        subfields.append(('u', inst))
                if not TEST:
                    AFFILIATIONS_DONE[affiliation_key] = inspire_affiliation
            if affiliation:
                subfields.append(('v', affiliation))
        #record_add_field(record, tag[0:3], tag[3], tag[4], \
        #                 subfields=subfields)
        #tag = '700__'
    #return print_rec(record)
    #print(record)
    return record


def preprocess_file_braces(read_data):
    """Try to close braces."""
    #print repr(read_data)
    read_data = re.sub(r'\\institute\{', \
                       r'\\section*{Affiliations}', read_data)
    read_data = re.sub(r'(\{[^\}]*)\n+', r'\1', read_data)
    read_data = re.sub(r'(\{[^\}]*\{[^\}]*\}[^\}]*)\n+', r'\1', read_data)
    read_data = re.sub(r'([\{\(\[])\s+', r'\1', read_data)
    read_data = re.sub(r'\s+([\}\)\]])', r'\1', read_data)
    read_data = re.sub(r'\\scriptsize\{(.*)\}', r'\1', read_data)
    read_data = read_data.replace(r'\\', '\n')
    read_data = re.sub(r'\,[ ]+\$\^', r'\n$^', read_data)
    #print repr(read_data)
    return read_data

def preprocess_file(read_data):
    """Get file into a form that can be properly processed."""

    read_data = preprocess_file_braces(read_data)

    #Process any user commands in latex.
    command_dict = {}
    for line in read_data.split('\n'):
        match = None
        if re.search('command', line):
            match = re.search(r'\\r?e?newcommand\*?\{\\(\w+)\}\{(.*)\}', line)
        elif re.search(r'\\def\\', line):
            match = re.search(r'\\def\\(\w+)\{(.*)\}', line)
        if match:
            command_value = match.group(2)
            if re.search(r'^\\\w', command_value):
                command_value = '\\' + command_value
            command_dict[match.group(1)] = command_value
    for key in command_dict:
        try:
            command_string = re.compile(r'\\%s\b' % key)
            read_data = re.sub(command_string, command_dict[key], read_data)
        except re.error:
            print('!!! Problem with user commands:', key, command_dict[key])
            sys.exit()

    read_data = read_data.replace('{+}', '{WXYZ}')

    for line in read_data.split('\n'):
    #    #\href{http://inspirehep.net/record/1068305}{J.~Alimena}$^{7}$
    #    match_obj = re.search(r'/record/(\d+).*$', line)
    #    if match_obj:
    #        for id_type in ['ORCID', 'INSPIRE']:
    #            id_num = get_hepnames_anyid_from_recid(match_obj.group(1),
    #                                                   id_type)
    #            if id_num:
    #                #print line
    #                line_new = re.sub(r'.*\}\{(.*)\}(\$\^.*)',
    #                                  r'\1 [' + id_num + r']\2', line)
    #                read_data = read_data.replace(line, line_new)
    #                #print line_new
    #                continue
    #    match_obj = re.search(r'record/(\d+)', line)
    #    if match_obj:
    #        try:
    #            inst = get_fieldvalues(match_obj.group(1), '110__u')[0]
    #            line_new = re.sub(r'\\href{http://inspirehep.net/record/\d+}',
    #                       inst + ' %', line)
    #            print(line_new)
    #            read_data = read_data.replace(line, line_new)
    #        except IndexError:
    #            pass

        #John Smith (University of Somewhere)
        if re.search(r'^[A-Z].* \(.*\)\s*$', line):
            line_new = re.sub(r'(.*)\s+\((.*)\)',
                              r'\\author{\1}\n\\affiliation{\2}', line)
            read_data = read_data.replace(line, line_new)

        #Josh~McFayden\affmark[1,3]
        if re.search(r'\\affmark\[', line):
            line_new = re.sub(r'\\affmark\[(.*)\]', r'$^{\1}$', line)
            read_data = read_data.replace(line, line_new)

        #\AddAuthor{C.~Lindsey}{11}{}{}
        if re.search(r'\\AddAuthor{', line):
            line_new = \
                     re.sub(r'\\AddAuthor{(.*)}{([^\}]*)}{([^\}]*)}{([^\}]*)}',
                              r'\1$^{\2,\3,\4}$', line)
            line_new = re.sub('[,]+}', '}', line_new)
            line_new = re.sub('{[,]+', '{', line_new)
            line_new = line_new.replace(',,', ',')
            read_data = read_data.replace(line, line_new)
        #\AddInstitute{1a}{Blah blah} \AddExternalInstitute
        line = line.replace('\\AddExternalInstitute', '\\AddInstitute')
        if re.search(r'\\AddInstitute{([^\}]+)}{', line):
            line_new = re.sub(r'\\AddInstitute{([^\}]+)}', r'$^{\1}$ ', line)
            read_data = read_data.replace('\\AddExternalInstitute', '\\AddInstitute')
            read_data = read_data.replace(line, line_new)

        #\firstname{C.-H.} \lastname{Yu} \inst{4}
        if re.search(r'\\firstname{', line) and re.search(r'\\inst{', line):
            line_new = re.sub(r'\\firstname{(.*)}\s*\\lastname{(.*)}\s*\\inst(\{.*\}).*',
                      r'YYYY\2, \1$^\3$', line)
            read_data = read_data.replace(line, line_new)
        #\firstname{C.-H.} \lastname{Yu}
        elif re.search(r'\\firstname{', line):
            #line_new = re.sub(r'\\firstname{([^\}]+)}\s*\\lastname{([^\}]+)}',
            line_new = re.sub(r'\\firstname{(.*)}\s*\\lastname{(.*)}',
                      r'YYYY\2, \1', line)
            read_data = read_data.replace(line, line_new)
        #I.J.~Arnquist\inst{10}
        if re.search(r'\\inst\{', line):
            line_new = re.sub(r'\\inst({[^\}]+\})', r'$^\1$', line)
            read_data = read_data.replace(line, line_new)
    #print "read_data =", read_data

    #Special treatment for BaBar
    for line in read_data.split('\n'):
        #BaBar \affiliation{Fermilab$^{a}$, SLAC$^{b}$}
        if re.search(r'\\affiliation\{.*\$\^\{?[abc]\}?\$', line):
            line_new = re.sub(r'\$\^\{?[abc]\}?\$', ' and ', line)
            read_data = read_data.replace(line, line_new)
        elif re.search(r'\\author\{.*\$\^\{?[abc]+\}?\$', line):
            line_new = re.sub(r'[ ]*\$\^\{?[abc]+\}?\$[ ]*', '', line)
            read_data = read_data.replace(line, line_new)
        elif re.search(r'\\author\{.*\\altaffiliation', line):
            line_new = re.sub(r'\\altaffiliation.*', '', line)
            read_data = read_data.replace(line, line_new)
        if VERBOSE:
            try:
                print('BABAR LINE =', line_new)
            except UnboundLocalError:
                pass

    #Special treatment for DES and Fermi-LAT and Planck
    astro_aff_counter = 0
    for line in read_data.split('\n'):
        #Get rid of newcommand lines now
        if re.search('newcommand', line):
            read_data = read_data.replace(line, '')
        if VERBOSE:
            print('ASTRO LINE =', line)
        if re.search(r'\\section\*\{Affiliations\}', line) or \
           re.search(r'\\institute\{\\small', line):
            astro_aff_counter = 1
        if astro_aff_counter and re.search(r'^\\item', line):
            line_new = \
                re.sub(r'^\\item', r'$^{' + str(astro_aff_counter) + r'}$', \
                line)
            read_data = read_data.replace(line, line_new, 1)
            astro_aff_counter += 1
        elif astro_aff_counter and re.search(r'\\goodbreak[ ]*$', line):
            line_new = \
                re.sub(r'(.*)[ ]*\\goodbreak[ ]*$', r'$^{' + \
                       str(astro_aff_counter) + r'}$ \1', \
                       line)
            read_data = read_data.replace(line, line_new, 1)
            if VERBOSE:
                print(astro_aff_counter, line)
                print(line_new)
            astro_aff_counter += 1
        elif astro_aff_counter and re.search(r'.\\and[ ]*$', line):
            line_new = \
                re.sub(r'(.*)[ ]*\\and[ ]*$', r'$^{' + \
                       str(astro_aff_counter) + r'}$ \1', \
                       line)
            read_data = read_data.replace(line, line_new, 1)
            astro_aff_counter += 1
    #print read_data


    #Special treatment for LIGO and Virgo
    pattern_au = re.compile(r"^([A-Z])[\~\.]([^-]*)([A-Z])([^A-Z]+)\s*\%\s*"
                         r"([a-z])([a-z]+)\.([a-z])([a-z]+)")
    pattern_af = re.compile(r"\\affiliation\s*\{(.*)\}\s*\%.*(\{\d+\})")
    for line in read_data.split('\n'):
        match = re.match(pattern_au, line)
        if match:
            if match.group(5).upper() == match.group(1) and \
               match.group(7).upper() == match.group(3):
                line_new = match.group(1) + match.group(6) + ' ' + \
                           match.group(2) + ' ' + match.group(3) + \
                           match.group(4)
                #print line_new, '\t\t', line
                read_data = read_data.replace(line, line_new)
        match = re.match(pattern_af, line)
        if match:
            line_new = "$^" + match.group(2) + "$" + match.group(1)
            #print line_new
            read_data = read_data.replace(line, line_new)

    #Remove spaces around braces and commas
    read_data = re.sub(r'[ ]*([\]\}\[\{\,])[ ]*', r'\1', read_data)
    read_data = re.sub(r'^[ ]+', '', read_data)

    read_data = re.sub(r'\-+', r'-', read_data)

    read_data = re.sub(r'%.*\n', '\n', read_data)
    read_data = re.sub(r'}\$,\s*', '}$\n', read_data)
    read_data = re.sub(r'\$\^(\w)\$,\s*', r'$^\1$\n', read_data)
    read_data = re.sub(r'\\thanks\{[^\}]+(0000-0[\d\-]+[\dX])[^\}]*\}',
                r'\\affiliation{\1}', read_data)
    read_data = re.sub(r'\}?\\thanks\{[^\}]+\}?', r'', read_data)
    read_data = re.sub(r'\\item\[(\$\^\{?\w+\}?\$)\]', r'\1', read_data)
    read_data = re.sub(r'\\llap\{(\$\S+\$)\}', r'\1 ', read_data)
    read_data = re.sub(r'\\textsuperscript\{([a-z\d\,]+)\}\{',
                       r'$^{\1$} \{', read_data)
    read_data = re.sub(r'\\textsuperscript\{([a-z\d\,]+)\}',
                       r'$^{\1$}\n', read_data)
    read_data = re.sub(r'\\address', r'\\affiliation', read_data)
    read_data = re.sub(r'\\affil\b', r'\\affiliation', read_data)
    read_data = re.sub(r'\\email\{', r'\\affiliation{', read_data)
    read_data = re.sub(r'}\s*\\affiliation', '}\n\\\\affiliation', read_data)
    read_data = re.sub(r'}\s*\\author', '}\n\\\\author', read_data)
    read_data = re.sub(r'[ ]*\\scriptsize[ ]+', '', read_data)
    read_data = re.sub(r'\\and[ ]+', '', read_data)
    read_data = re.sub(r'\$\s*\^', '$^', read_data)
    if VERBOSE:
        print('read_data =', read_data)
    read_data = re.sub(r'Irefn{(\w+)}\\Aref{(\w+)}\\Aref{(\w+)}', \
                       r'Irefn{\1,\2,\3}', read_data)
    read_data = re.sub(r'Irefn+\{(.*)\}\\?A?r?e?f?s?\{(.*)\}', \
                       r'Irefn{\1,\2}', read_data)
    read_data = re.sub(r'Arefs?{(\w+)}', r'Irefn{\1}', read_data)
    read_data = re.sub(r'\\Idef{(\w+)}', r'$^{\1}$', read_data)
    #read_data = \
    #    re.sub(r'(\w\.?)[ \,]*\\(inst|altaffilmark|Irefn)\{(.*)\}', \
    #           r'\1$^{\3}$', read_data)
    read_data = \
        re.sub(r'[ \,]*\\(inst|altaffilmark|Irefn|thanksref)\{([^\}]+)\}', \
               r'$^{\2}$', read_data)
    #\altaffiltext{2}{Fermilab, Batavia}
    read_data = \
        re.sub(r'\\(altaffiltext|thankstext)\{([\w\,\-]+)\}\{(.*)\}', \
               r'$^{\2}$ \3', read_data)
    read_data = \
        re.sub(r'\\item\s*\\[IA]def\{([\w\,\-]+)\}\{(.*)\}', r'$^{\1}$ \2', \
               read_data)
    read_data = \
        re.sub(r'\\[IA]def\{([\w\,\-]+)\}\{(.*)\}', r'$^{\1}$ \2', \
               read_data)
    read_data = \
        re.sub(r'(.*)\s*\\label\{(.*)\}', r'$^{\2}$ \1', \
               read_data)
    #\author[b,c]{M. Zimmermann} \affiliation[b]{Fermilab}
    read_data = \
        re.sub(r'\\author\[([\w\,\-]+)\]\{(.*)\}', r'\2$^{\1}$', read_data)
    read_data = \
        re.sub(r'\\affiliation\[([\w\,\-]+)\]\{(.*)\}', r'$^{\1}$ \2', \
               read_data)
    #\author{M. Zimmermann$^{b,c}$} \affiliation{$^{b}$Fermilab} remove \author
    read_data = \
        re.sub(r'\\author\{(.*\$\^\{?[\w\,\-]+\}?\$)\}', r'\1', read_data)
    read_data = \
        re.sub(r'\\affiliation\{(\$\^\{?[\w\,\-]+\}?\$.*)\}', r'\1', read_data)

    read_data = re.sub(r'[\, ]+\}', '}', read_data)
    read_data = re.sub(r'[\, ]+\$\^', '$^', read_data)
    #print read_data
    new_read_data = []
    for line in read_data.split('\n'):
        if re.search('abstract', line, re.IGNORECASE) and astro_aff_counter < 1:
            break
        new_read_data.append(line)
    if VERBOSE:
        print('new_read_data =', new_read_data)
    return new_read_data

def process_ieee(eprint):
    """Obtains authors and affiliations from ieee link
    """
    request = requests.get(eprint)
    uncleanjson = [line for line in request.text.split('\n') if
        line.lstrip().startswith('global.document.metadata=')][0]
    cleanjsonmatch = re.search(r'metadata\=(\{.*?\});$', uncleanjson)
    if cleanjsonmatch:
        cleanjson = cleanjsonmatch.group(1)
        json_acceptable_string = cleanjson.replace('"', '\"')
        json_dict = json.loads(json_acceptable_string)
        cleanauths = {}
        try:
            auths = json_dict['authors']
        except KeyError:
            print('No IEEE authors found')
            return None
        for auth in auths:
            auth['affiliation'] = re.sub(r'^\s+', '', auth['affiliation'])
            if 'e-mail' in auth['affiliation']:
                match_obj = re.match(r'(.*) \(e\-mail: (.*)\)',
                            auth['affiliation'])
                auth['affiliation'] = match_obj.group(1)
                auth['email']       = match_obj.group(2)
            cleanauths[auths.index(auth)+1] = \
                [process_author_name(auth['name']), [auth['affiliation']]]
            for id_type in ('orcid', 'email'):
                if id_type in auth:
                    cleanauths[auths.index(auth)+1][1].append(auth[id_type])
        #try:
        #    doi = json_dict['doi']
        #except KeyError:
        #    print('No doi found')

    print('Number of authors:', len(cleanauths))
    return create_xml(author_dict=cleanauths)

def process_file(eprint, file_type='tex'):
    """Obtain authors and affiliations from file.
       Creates a dictionary, author_dict, of the form
       {position:[author name, [list of affiliations]]
    """

    with open(eprint.replace('/', '-') + '.' + file_type, 'r') as input_file:
        read_data = input_file.read()
    read_data = preprocess_file(read_data)
    author_position = 0
    author_dict = {}
    affiliation_dict = {}
    babar_flag = False
    reverse_babar_flag = False
    author_previous = False
    author_affiliation = None
    for line in read_data:
        #Find author/affiliations for $^{1}$
        match = re.search(r'^(\\?\"?[A-Z].*)\$\^\{?([\w\-\s\,]+)\}?\$', line)
        if match:
            author = match.group(1)
            author = process_author_name(author)
            author_dict[author_position] = [author, match.group(2).split(',')]
            author_position += 1
        match = re.search(r'^\$\^\{?([\w\-\s\,]+)\}?\$\s*(.*)', line)
        if match:
            affiliation_dict[match.group(1)] = match.group(2)
            if VERBOSE:
                print('aff_dict', match.group(1), ':',
                       affiliation_dict[match.group(1)])
        #elif VERBOSE and re.search(r'\$\^', line):
        #    print "NO MATCH:", line
        #Find author/affiliations for \\author, \\affiliation
        match = re.search(r'\\author\{(.*)\}', line)
        if match:
            if author_previous:
                babar_flag = True
            if babar_flag:
                author = re.sub(r'\$\^\{?[abc]+\}\$', '', author)
            author = process_author_name(match.group(1))
            author_dict[author_position] = [author, []]
            if reverse_babar_flag:
                for key in author_dict:
                    if not author_dict[key][1]:
                        author_dict[key][1].append(author_affiliation)
            author_position += 1
            author_previous = True
        else:
            author_previous = False
        match = re.search(r'\\affiliation\{(.*)\}', line)
        if match and babar_flag:
            author_affiliation = match.group(1)
            author_affiliation = re.sub(r'\$\^\{?[abc]+\}?\$', ' and ', \
                                        author_affiliation)
            for key in author_dict:
                if not author_dict[key][1]:
                    #author_dict[key][1].append(match.group(1))
                    author_dict[key][1].append(author_affiliation)
        elif match:
            try:
                author_dict[author_position - 1][1].append(match.group(1))
            except KeyError:
                #print 'BaBar-style', author_position,  match.group(1)
                #pass
                reverse_babar_flag = True
                author_affiliation = match.group(1)
    if VERBOSE:
        print('author_dict =', author_dict)
    print('Number of authors:', author_position)
    if affiliation_dict:
        #for key in sorted(affiliation_dict):
        #    print key, ':', affiliation_dict[key]
        for key in author_dict:
            for position, affiliation_key in enumerate(author_dict[key][1]):
                if affiliation_key not in affiliation_dict:
                    print('Unknown affkey {0} for {1}'.format(
                          affiliation_key, author_dict[key]))
                    continue
                try:
                    author_dict[key][1][position] = \
                        affiliation_dict[affiliation_key]
                except KeyError:
                    print('Unknown affkey for', author_dict[key])


    return create_xml(author_dict=author_dict)

def main(eprint):
    """Get the author list."""
    filename = 'tmp_' + __file__

    eprint_tex = eprint.replace('/', '-') + ".tex"
    eprint_xml = eprint.replace('/', '-') + ".xml"
    file_type = None
    if VERBOSE:
        print('eprint =', eprint)
    if os.path.exists(eprint_tex) or os.path.exists(eprint_xml):
        file_type = 'tex'
    elif re.search(r'^[a-zA-Z\-]+/\d{7}$', eprint) or \
         re.search(r'^\d{4}\.\d{4}\d?$', eprint):
        file_type = '1'
    elif eprint.startswith('10.1109'):
        file_type = '2'
    else:
        file_type = input("""Choose paper type:
1 arXiv
2 ieee
""")
    if file_type in ['1', '2']:
        if VERBOSE:
            print('file_type', file_type)
        if file_type == '1':
            file_type = 'tex'
            if not download_source(eprint):
                return
        elif file_type == '2':
            file_type = 'ieee'
            if 'ieee' in eprint:
                filename = re.sub('.py', '_' + re.sub(r'\D', '', eprint) + \
                          '_correct.out', filename)
            else:
                filename = re.sub('.py', '_' +
                      eprint.replace('/', '-').replace('.', '-') + \
                      '_correct.out', filename)
                eprint = 'http://dx.doi.org/'+ eprint
        else:
            print('Invalid choice')
            sys.exit()
    if os.path.exists(eprint_xml):
        print(eprint_xml)
        sys.exit()
    if '_correct.out' not in filename:
        filename = re.sub('.py', '_' + eprint.replace('/', '-') + \
                      '_correct.out', filename)
    output = open(filename,'w')
    output.write('<collection>')
    if file_type == 'tex':
        update = process_file(eprint)
    elif file_type == 'ieee':
        update = process_ieee(eprint)
    if update:
        output.write(update)
    output.write('</collection>')
    output.close()
    #print(filename)
    os.unlink(filename)

    filename = __file__
    filename = filename.replace('.py', '.log')
    log = open(filename, 'a')
    date_time_stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    date_time_stamp = date_time_stamp + ' ' + eprint + '\n'
    log.write(date_time_stamp)
    log.close()
    print(filename)
    recid = get_recid(eprint)
    print('https://inspirehep.net/literature/' + str(recid))

if __name__ == '__main__':

    BIB = DAT = TEST = VERBOSE = False

    try:
        OPTIONS, ARGUMENTS = getopt.gnu_getopt(sys.argv[1:], 'bdtv')
    except getopt.error:
        print('Error: you tried to use an unknown option')
        sys.exit(0)

    for option, argument in OPTIONS:
        if option == '-b':
            BIB = True
        if option == '-d':
            DAT = True
        if option == '-t':
            TEST = True
        if option == '-v':
            VERBOSE = True

    if TEST:
        def get_aff(aff):
            """Does nothing to affiliation."""
            return [aff]
    else:
        #from hep_aff import get_aff
        pass

    if len(ARGUMENTS) != 1:
        print('You didn\'t specify an eprint number')
        sys.exit(0)

    try:
        try:
            EPRINT = ARGUMENTS[0]
            #main(EPRINT)
        except IndexError:
            print('Bad input', EPRINT)
            sys.exit()
        main(EPRINT)

    except KeyboardInterrupt:
        print('Exiting')



    #else:
    #    try:
    #        EPRINT = ARGUMENTS[0]
    #        main(EPRINT)
    #    except IndexError:
    #        print "Bad input", EPRINT
    #    except KeyboardInterrupt:
    #        print 'Exiting'
