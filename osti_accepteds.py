'''Script to load an unload pickled intbitset of all OSTI accepted IDs'''

import datetime
import pickle
import os

from os.path import exists

DIRECTORY = '/web/sites/ccd.fnal.gov/data/osti_accepteds/'
OSTI_ACCEPTEDS_FILE = 'osti_accepteds_file.p'
OSTI_ACCEPTEDS_FILE = DIRECTORY + OSTI_ACCEPTEDS_FILE

def check_in_accepteds(osti_id=None):
    '''Check to see if an osti_id is in the list of accepteds.'''

    if osti_id is None:
        return False
    try:
        osti_id = int(osti_id)
    except ValueError:
        print(f'check_in_accepteds: {osti_id} cannot be an osti ID')
        return False
    if osti_id in retrieve_accepteds():
        return True
    return False


def retrieve_accepteds():
    '''Get a list of the OSTI IDs all accepted PDFs sent to OSTI'''

    try:
        osti_accepteds = pickle.load(open(OSTI_ACCEPTEDS_FILE, 'rb'))
        #print('Number of accepteds retrieved:', len(osti_accepteds))
        return osti_accepteds
    except pickle.UnpicklingError:
        print('No existing OSTI accepteds file found')
        return None

def store_accepteds(osti_accepteds):
    '''Add OSTI IDs of new accpted PDFs'''

    if exists(OSTI_ACCEPTEDS_FILE):
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_file = OSTI_ACCEPTEDS_FILE + '.' + stamp
        if exists(backup_file):
            os.remove(backup_file)
        os.rename(OSTI_ACCEPTEDS_FILE, backup_file)
    with open(OSTI_ACCEPTEDS_FILE, 'wb') as fname:
        pickle.dump(osti_accepteds, fname)
    print('Number of accepteds stored:', len(osti_accepteds))
