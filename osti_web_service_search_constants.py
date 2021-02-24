SEARCH_DATE = 'dadd:2012->2025'

SEARCH_FNAL = '_collections:Fermilab report_numbers.value:Fermilab*'
SEARCH_FNAL += ' -report_numbers.value:"fermilab-code-*"'

SEARCH_OSTI = 'external_system_identifiers.schema:osti'

SEARCH_DEFAULT = f'{SEARCH_FNAL} {SEARCH_DATE} -{SEARCH_OSTI}'

SEARCH_ACCEPTED = ['urls.description:"Fermilab Accepted Manuscript"',
'urls.description:"open access fulltext"',
'documents.description:"open access fulltext"',
'documents.description:"article from scoap3"',
'documents.description:"Fulltext from Publisher"',
'urls.description:"Fulltext from Publisher"']

SEARCH_ACCEPTED_END = f' doi:10* {SEARCH_FNAL} {SEARCH_OSTI}'
