import json
import logging
import os
from datetime import datetime, timedelta

import requests

from secure.secrets import users


class ChurchToolsApi:
    def __init__(self, domain, ct_token):
        self.session = None
        self.domain = domain

        self.ajax_song_last_update = None
        self.ajax_song_cache = []

        self.login_ct_rest_api(ct_token)

    def login_ct_ajax_api(self, user=list(users.keys())[0], pswd=""):
        """
        Login function using AJAX with Username and Password
        :param user: Username
        :param pswd: Password - default safed in secure.token.user dict for tests
        :return: if login successful
        """
        self.session = requests.Session()
        login_url = self.domain + '/?q=login/ajax&func=login'
        data = {'email': user, 'password': pswd}

        response = self.session.post(url=login_url, data=data)
        if response.status_code == 200:
            logging.info('Ajax User Login Successful')
            self.session.headers['CSRF-Token'] = self.get_ct_csrf_token()
            return json.loads(response.content)["status"] == 'success'
        else:
            logging.warning("Token Login failed with {}".format(response.content.decode()))
            return False

    def login_ct_rest_api(self, login_token):
        """
        Authorization: Login<token>
        If you want to authorize a request, you need to provide a Login Token as
        Authorization header in the format {Authorization: Login<token>}
        Login Tokens are generated in "Berechtigungen" of User Settings
        :param login_token: token to be used for login into CT
        :return: if login successful
        """

        self.session = requests.Session()
        login_url = self.domain + '/api/whoami'
        headers = {"Authorization": 'Login ' + login_token}
        response = self.session.get(url=login_url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            logging.info('Token Login Successful as {}'.format(response_content['data']['email']))
            self.session.headers['CSRF-Token'] = self.get_ct_csrf_token()
            return json.loads(response.content)['data']['id'] > 0
        else:
            logging.warning("Token Login failed with {}".format(response.content.decode()))
            return False

    def get_ct_csrf_token(self):
        """
        Requests CSRF Token https://hilfe.church.tools/wiki/0/API-CSRF
        This method was created when debugging file upload
        storing and transmitting CSRF token in headers is required for all legacy AJAX API calls unless disabled by admin
        e.g. self.session.headers['CSRF-Token'] = self.get_ct_csrf_token()
        :return: str token
        """
        url = self.domain + '/api/csrftoken'
        response = self.session.get(url=url)  # , headers=headers)
        if response.status_code == 200:
            csrf_token = json.loads(response.content)["data"]
            logging.info("CSRF Token erfolgreich abgerufen {}".format(csrf_token))
            return csrf_token
        else:
            logging.warning("CSRF Token not updated because of Response {}".format(response.content.decode()))

    def check_connection_ajax(self):
        """
        Checks whether a successful connection with the given token can be initiated using the legacy AJAX API
        :return:
        """
        url = self.domain + '/?q=churchservice/ajax&func=getAllFacts'
        headers = {
            'accept': 'application/json'
        }
        response = self.session.post(url=url, headers=headers)
        if response.status_code == 200:
            logging.debug("Response AJAX Connection successful")
            return True
        else:
            logging.debug("Response AJAX Connection failed with {}".format(json.load(response.content)))
            return False

    def get_persons(self, **kwargs):
        """
        Function to get list of all or a person from CT
        :param kwargs: optional keywords as listed
        :keyword ids: list of a ids filter
        :keyword returnAsDict: true if should return a dict instead of list (not combineable if serviceId)
        :return: list of user dicts or a single user dict if only one
        """
        url = self.domain + '/api/persons'
        params = {}
        if 'ids' in kwargs.keys():
            params['ids[]'] = kwargs['ids']

        headers = {
            'accept': 'application/json'
        }
        response = self.session.get(url=url, params=params, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['data'].copy()

            logging.debug("First response of GET Persons successful {}".format(response_content))

            if len(response_data) == 0:
                logging.warning('Requesting users {} returned an empty response - '
                                'make sure the user has correct permissions'.format(params))

            if 'meta' not in response_content.keys():  # Shortcut without Pagination
                return response_data

            # Long part extending results with pagination
            while response_content['meta']['pagination']['current'] \
                    < response_content['meta']['pagination']['lastPage']:
                logging.info("page {} of {}".format(response_content['meta']['pagination']['current'],
                                                    response_content['meta']['pagination']['lastPage']))
                params = {'page': response_content['meta']['pagination']['current'] + 1}
                response = self.session.get(url=url, headers=headers, params=params)
                response_content = json.loads(response.content)
                response_data.extend(response_content['data'])

            if 'returnAsDict' in kwargs and not 'serviceId' in kwargs:
                if kwargs['returnAsDict']:
                    result = {}
                    for item in response_data:
                        result[item['id']] = item
                    response_data = result

            logging.debug("Persons load successful {}".format(response_data))
            return response_data[0] if len(response_data) == 1 else response_data
        else:
            logging.info("Persons requested failed: {}".format(response.status_code))
            return None

    def get_songs(self, **kwargs):
        # song_id=None):
        """ Gets list of all songs from the server
        :key kwargs song_id: optional filter by song id
        :return: JSON Response of all songs from ChurchTools or single object
        """

        url = self.domain + '/api/songs'
        if "song_id" in kwargs.keys():
            url = url + '/{}'.format(kwargs["song_id"])
        headers = {
            'accept': 'application/json'
        }
        response = self.session.get(url=url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['data'].copy()
            logging.debug("First response of GET Songs successful {}".format(response_content))

            if 'meta' not in response_content.keys():  # Shortcut without Pagination
                return response_data

            # Long part extending results with pagination
            while response_content['meta']['pagination']['current'] \
                    < response_content['meta']['pagination']['lastPage']:
                logging.info("page {} of {}".format(response_content['meta']['pagination']['current'],
                                                    response_content['meta']['pagination']['lastPage']))
                params = {'page': response_content['meta']['pagination']['current'] + 1}
                response = self.session.get(url=url, headers=headers, params=params)
                response_content = json.loads(response.content)
                response_data.extend(response_content['data'])

            return response_data
        else:
            if "song_id" in kwargs.keys():
                logging.info("Did not find song ({}) with CODE {}".format(kwargs["song_id"], response.status_code))
            else:
                logging.warning("Something went wrong fetching songs: CODE {}".format(response.status_code))

    def get_song_ajax(self, song_id=None, require_update_after_seconds=10):
        """
        Legacy AJAX function to get a specific song
        used to e.g. check for tags requires requesting full song list
        for efficiency reasons songs are cached and not updated unless older than 15sec or update_required
        :param song_id: the id of the song to be searched for
        :type song_id: int
        :param require_update_after_seconds: number of seconds after which an update of ajax song cache is required
            defaults to 10 sedonds
        :type require_update_after_seconds: int
        :return: response content interpreted as json
        :rtype: dict
        """

        if self.ajax_song_last_update is None:
            require_update = True
        else:
            require_update = self.ajax_song_last_update + timedelta(seconds=10) < datetime.now()
        if require_update:
            url = self.domain + '/?q=churchservice/ajax&func=getAllSongs'
            response = self.session.post(url=url)
            self.ajax_song_cache = json.loads(response.content)['data']['songs']
            self.ajax_song_last_update = datetime.now()

        song = self.ajax_song_cache[str(song_id)]

        return song

    def get_song_category_map(self):
        """
        Helpfer function creating requesting CT metadata for mapping of categories
        :return: a dictionary of CategoryName:CTCategoryID
        :rtype: dict
        """

        url = self.domain + '/api/event/masterdata'
        headers = {
            'accept': 'application/json'
        }
        response = self.session.get(url=url, headers=headers)
        response_content = json.loads(response.content)
        song_categories = response_content['data']['songCategories']
        song_category_dict = {}
        for item in song_categories:
            song_category_dict[item['name']] = item['id']

        return song_category_dict

    def get_groups(self, group_id=None):
        """ Gets list of all groups
        :param group_id: optional filter by group id
        :return dict mit allen Gruppen
        """
        url = self.domain + '/api/groups'
        if group_id is not None:
            url = url + '/{}'.format(group_id)
        headers = {
            'accept': 'application/json'
        }
        response = self.session.get(url=url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['data'].copy()
            logging.debug("First response of Groups successful {}".format(response_content))

            if 'meta' not in response_content.keys():  # Shortcut without Pagination
                return response_data

            # Long part extending results with pagination
            while response_content['meta']['pagination']['current'] \
                    < response_content['meta']['pagination']['lastPage']:
                logging.info("page {} of {}".format(response_content['meta']['pagination']['current'],
                                                    response_content['meta']['pagination']['lastPage']))
                params = {'page': response_content['meta']['pagination']['current'] + 1}
                response = self.session.get(url=url, headers=headers, params=params)
                response_content = json.loads(response.content)
                response_data.extend(response_content['data'])

            return response_data
        else:
            logging.warning("Something went wrong fetiching groups: {}".format(response.status_code))

    def file_upload(self, filename_path_for_upload, domain_type, domain_identifier,
                    custom_file_name=None,
                    overwrite=False):
        """
        Helper function to upload an attachment to any module of ChurchTools
        :param filename_path_for_upload: file to be opened e.g. with open('media/pinguin.png', 'rb')
        :param domain_type:  The domain type, currently supported are 'avatar', 'groupimage', 'logo', 'attatchments',
         'html_template', 'service', 'song_arrangement', 'importtable', 'person', 'familyavatar', 'wiki_.?'.
        :param domain_identifier: ID of the object in ChurchTools
        :param custom_file_name: optional file name - if not specified the one from the file is used
        :param overwrite: if true delete existing file before upload of new one to replace \
        it's content instead of creating a copy
        :return:
        """

        file_to_upload = open(filename_path_for_upload, 'rb')

        url = '{}/api/files/{}/{}'.format(self.domain, domain_type, domain_identifier)

        if overwrite:
            logging.debug("deleting old file {} before new upload".format(file_to_upload))
            delete_file_name = file_to_upload.name.split('/')[-1] if custom_file_name is None else custom_file_name
            self.file_delete(domain_type, domain_identifier, delete_file_name)

        # add files as files form data with dict using 'files[]' as key and (tuple of filename and fileobject)
        if custom_file_name is None:
            files = {'files[]': (file_to_upload.name.split('/')[-1], file_to_upload)}
        else:
            if '/' in custom_file_name:
                logging.warning('/ in file name ({}) will fail upload!'.format(custom_file_name))
                files = {}
            else:
                files = {'files[]': (custom_file_name, file_to_upload)}

        response = self.session.post(url=url, files=files)
        file_to_upload.close()

        """
        # Issues with HEADERS in Request module when using non standard 'files[]' key in POST Request
        # Workaround for ChurchTools - generate session with /api/whoami GET request and reuse it
        # Requests module usually automatically completes required header Params e.g. Content-Type ...
        # in case manual header e.g. for AUTH is used, headers don't auto complete
        # and server rejects messsages or data is ommited 
        # Error Code 500 is also missing in API documentation
        
        headers = {'Authorization': 'Login GEHEIM'}
        response_test = requests.post(url=url, headers=headers, files=files)
        #> this fails !
        """

        if response.status_code == 200:
            try:
                response_content = json.loads(response.content)
                logging.debug("Upload successful {}".format(response_content))
            except:
                logging.warning(response.content.decode())
        else:
            logging.warning(response.content.decode())

    def file_delete(self, domain_type, domain_identifier, filename_for_selective_delete=None):
        """
        Helper function to delete ALL attachments of any specified module of ChurchTools#
        or identifying individual file_name_ids and deleting specifc files only
        :param domain_type:  The domain type, currently supported are 'avatar', 'groupimage', 'logo', 'attatchments',
         'html_template', 'service', 'song_arrangement', 'importtable', 'person', 'familyavatar', 'wiki_.?'.
        :param domain_identifier: ID of the object in ChurchTools
        :param filename_for_selective_delete: name of the file to be deleted - all others will be kept
        :return: if successful
        """
        url = self.domain + '/api/files/{}/{}'.format(domain_type, domain_identifier)

        if filename_for_selective_delete is not None:
            response = self.session.get(url=url)
            files = json.loads(response.content)['data']
            selective_file_ids = [item["id"] for item in files if item['name'] == filename_for_selective_delete]
            for current_file_id in selective_file_ids:
                url = self.domain + '/api/files/{}'.format(current_file_id)
                response = self.session.delete(url=url)

        # Delete all Files for the id online
        else:
            response = self.session.delete(url=url)

        return response.status_code == 204  # success code for delete action upload

    def create_song(self, title: str, songcategory_id: int, author='', copyright='', ccli='', tonality='', bpm='',
                    beat=''):
        """
        Method to create a new song using legacy AJAX API
        Does not check for existing duplicates !
        function endpoint see https://api.church.tools/function-churchservice_addNewSong.html
        name for params reverse engineered based on web developer tools in Firefox and live churchTools instance

        :param title: Title of the Song
        :param songcategory_id: int id of site specific songcategories (created in CT Metadata) - required
        :param author: name of author or authors, ideally comma separated if multiple - optional
        :param copyright: name of organization responsible for rights distribution - optional
        :param ccli: CCLI ID see songselect.ccli.com/ - using "-" if empty on purpose - optional
        :param tonality: empty or specific string used for tonaly - see ChurchTools for details e.g. Ab,A,C,C# ... - optional
        :param bpm: Beats per Minute - optional
        :param beat: Beat - optional

        :return: int song_id: ChurchTools song_id of the Song created
        """
        url = self.domain + '/?q=churchservice/ajax&func=addNewSong'

        data = {
            'bezeichnung': title,
            'songcategory_id': songcategory_id,
            'author': author,
            'copyright': copyright,
            'ccli': ccli,
            'tonality': tonality,
            'bpm': bpm,
            'beat': beat
        }

        response = self.session.post(url=url, data=data)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            new_id = int(response_content['data'])
            logging.debug("Song created successful with ID={}".format(new_id))
            return new_id

        else:
            logging.info("Creating song failed with {}".format(response.status_code))
            return None

    def edit_song(self, song_id: int, songcategory_id=None, title=None, author=None, copyright=None, ccli=None,
                  practice_yn=None, ):
        """
        Method to EDIT an existing song using legacy AJAX API
        Changes are only applied to fields that have values in respective param
        None is considered empty while '' is an empty text which clears existing values

        function endpoint see https://api.church.tools/function-churchservice_editSong.html
        name for params reverse engineered based on web developer tools in Firefox and live churchTools instance
        NOTE - BPM and BEAT used in create are part of arrangement and not song therefore not editable in this method

        :param song_id: ChurchTools site specific song_id which should be modified - required

        :param title: Title of the Song
        :param songcategory_id: int id of site specific songcategories (created in CT Metadata)
        :param author: name of author or authors, ideally comma separated if multiple
        :param copyright: name of organization responsible for rights distribution
        :param ccli: CCLI ID see songselect.ccli.com/ - using "-" if empty on purpose
        :param practice_yn: bool as 0 and 1 - additional param which does not exist in create method!

        :return: response item
        """

        # system/churchservice/churchservice_db.php
        url = self.domain + '/?q=churchservice/ajax&func=editSong'

        existing_song = self.get_songs(song_id=song_id)

        data = {
            'id': song_id if song_id is not None else existing_song['name'],
            'bezeichnung': title if title is not None else existing_song['name'],
            'songcategory_id': songcategory_id if songcategory_id is not None else existing_song['category']['id'],
            'author': author if author is not None else existing_song['author'],
            'copyright': copyright if copyright is not None else existing_song['copyright'],
            'ccli': ccli if ccli is not None else existing_song['ccli'],
            'practice_yn': practice_yn if practice_yn is not None else existing_song['shouldPractice'],
        }

        response = self.session.post(url=url, data=data)
        return response

    def delete_song(self, song_id: int):
        """
        Method to DELETE a song using legacy AJAX API
        name for params reverse engineered based on web developer tools in Firefox and live churchTools instance

        :param song_id: ChurchTools site specific song_id which should be modified - required

        :return: response item
        """

        # system/churchservice/churchservice_db.php
        url = self.domain + '/?q=churchservice/ajax&func=deleteSong'

        data = {
            'id': song_id,
        }

        response = self.session.post(url=url, data=data)
        return response

    def add_song_tag(self, song_id: int, song_tag_id: int):
        """
        Method to add a song tag using legacy AJAX API on a specific song
        reverse engineered based on web developer tools in Firefox and live churchTools instance

        re-adding existing tag does not cause any issues
        :param song_id: ChurchTools site specific song_id which should be modified - required
        :param song_tag_id: ChurchTools site specific song_tag_id which should be added - required

        :return: response item
        """
        url = self.domain + '/?q=churchservice/ajax&func=addSongTag'

        data = {
            'id': song_id,
            'tag_id': song_tag_id
        }

        response = self.session.post(url=url, data=data)
        return response

    def remove_song_tag(self, song_id: int, song_tag_id: int):
        """
        Method to remove a song tag using legacy AJAX API on a specifc song
        reverse engineered based on web developer tools in Firefox and live churchTools instance

        re-removing existing tag does not cause any issues
        :param song_id: ChurchTools site specific song_id which should be modified - required
        :param song_tag_id: ChurchTools site specific song_tag_id which should be added - required

        :return: response item
        """
        url = self.domain + '/?q=churchservice/ajax&func=delSongTag'

        data = {
            'id': song_id,
            'tag_id': song_tag_id
        }

        response = self.session.post(url=url, data=data)
        return response

    def get_song_tags(self, song_id: int):
        """
        Method to get a song tag workaround using legacy AJAX API for getSong
        :param song_id: ChurchTools site specific song_id which should be modified - required
        :return: response item
        """
        song = self.get_song_ajax(song_id)
        return song['tags']

    def contains_song_tag(self, song_id: int, song_tag_id: int):
        """
        Helper which checks if a specifc song_tag_id is present on a song
        :param song_id: ChurchTools site specific song_id which should checked
        :param song_tag_id: ChurchTools site specific song_tag_id which should be searched for
        :return: bool if present
        """
        tags = self.get_song_tags(song_id)
        return str(song_tag_id) in tags

    def get_songs_by_tag(self, song_tag_id: int):
        """
        Helper which returns all songs that contain have a specific tag
        :param song_tag_id: ChurchTools site specific song_tag_id which should be searched for
        :return: list of songs
        """
        songs = self.get_songs()
        songs_dict = {song['id']: song for song in songs}

        filtered_song_ids = []
        for id in songs_dict.keys():
            if self.contains_song_tag(id, song_tag_id):
                filtered_song_ids.append(id)

        result = [songs_dict[song_id] for song_id in filtered_song_ids]

        return result

    def get_events(self, **kwargs):
        """
        Method to get all the events from given timespan or only the next event
        :param kwargs: optional params to modify the search criteria
        :key eventId: number of event for single event lookup
        :key from_: str with starting date in format YYYY-MM-DD - added _ to name as opposed to api because of reserved keyword
        :key to_: str end date in format YYYY-MM-DD ONLY allowed with from_ - added _ to name as opposed to api because of reserved keyword
        :key canceled: bool If true, include also canceled events
        :key direction: direction of output 'forward' or 'backward' from the date defined by parameter 'from'
        :key limit: limits the number of events - Default = 1, if all events shall be retrieved insert 'None', only applies if direction is specified
        :key include: if Parameter is set to 'eventServices', the services of the event will be included
        :return: list of events or a single event as dict (if only one)
        """
        url = self.domain + '/api/events'

        headers = {
            'accept': 'application/json'
        }
        params = {}

        if 'eventId' in kwargs.keys():
            url += '/{}'.format(kwargs['eventId'])

        else:
            if 'from_' in kwargs.keys():
                if len(kwargs['from_']) == 10:
                    params['from'] = kwargs['from_']
            if 'to_' in kwargs.keys() and 'from_' in kwargs.keys():
                if len(kwargs['to_']) == 10:
                    params['to'] = kwargs['to_']
            elif 'to_' in kwargs.keys():
                logging.warning('Use of to_ is only allowed together with from_')
            if 'canceled' in kwargs.keys():
                params['canceled'] = kwargs['canceled']
            if 'direction' in kwargs.keys():
                params['direction'] = kwargs['direction']
            if 'limit' in kwargs.keys() and 'direction' in kwargs.keys():
                params['limit'] = kwargs['limit']
            elif 'direction' in kwargs.keys():
                logging.warning('Use of limit is only allowed together with direction keyword')
            if 'include' in kwargs.keys():
                params['include'] = kwargs['include']

        response = self.session.get(url=url, params=params, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['data'].copy()
            logging.debug("First response of Events successful {}".format(response_content))

            if 'meta' not in response_content.keys():  # Shortcut without Pagination
                return response_data

            if 'pagination' not in response_content['meta'].keys():
                if len(response_data) == 1:
                    return response_data[0]
                else:
                    return response_data

            # Long part extending results with pagination
            # TODO #1 copied from other method unsure if pagination works the same as with groups
            while response_content['meta']['pagination']['current'] \
                    < response_content['meta']['pagination']['lastPage']:
                logging.info("page {} of {}".format(response_content['meta']['pagination']['current'],
                                                    response_content['meta']['pagination']['lastPage']))
                params = {'page': response_content['meta']['pagination']['current'] + 1}
                response = self.session.get(url=url, headers=headers, params=params)
                response_content = json.loads(response.content)
                response_data.extend(response_content['data'])

            return response_data
        else:
            logging.warning("Something went wrong fetching events: {}".format(response.status_code))

    def get_AllEventData_ajax(self, eventId: int):
        """
        Reverse engineered function from legacy AJAX API which is used to get all event data for one event
        Required to read special params not yet included in REST getEvents()
        Legacy AJAX request might stop working with any future release ... CSRF-Token is required in session header
        :param eventId: number of the event to be requested
        :return:
        """
        url = self.domain + '/index.php'
        headers = {
            'accept': 'application/json'
        }
        params = {'q': 'churchservice/ajax'}
        data = {
            'id': eventId,
            'func': 'getAllEventData'
        }
        response = self.session.post(url=url, headers=headers, params=params, data=data)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            if len(response_content['data']) > 0:
                response_data = response_content['data'][str(eventId)]
                logging.debug("AJAX Event data {}".format(response_data))
                return response_data
            else:
                logging.info("AJAX All Event data not successful - no event found: {}".format(response.status_code))
                return None
        else:
            logging.info("AJAX All Event data not successful: {}".format(response.status_code))
            return None

    def get_event_services_counts_ajax(self, eventId, **kwargs):
        """
        retrieve the number of services currently set for one specific event id
        optionally get the number of services for one specific id on that event only
        :param eventId: id number of the calendar event
        :type eventId: int
        :param kwargs: keyword arguments either serviceId or service_group_id
        :key serviceId: id number of the service type to be filtered for
        :key serviceGroupId: id number of the group of services to request
        :return: dict of service types and the number of services required for this event
        :rtype: dict
        """

        event = self.get_events(eventId=eventId)

        if 'serviceId' in kwargs.keys() and 'serviceGroupId' not in kwargs.keys():
            service_count = 0
            for service in event['eventServices']:
                if service['serviceId'] == kwargs['serviceId']:
                    service_count += 1
            return {kwargs['serviceId']: service_count}
        elif 'serviceId' not in kwargs.keys() and 'serviceGroupId' in kwargs.keys():
            all_services = self.get_services()
            serviceGroupServiceIds = [service['id'] for service in all_services
                                      if service['serviceGroupId'] == kwargs['serviceGroupId']]

            services = {}
            for service in event['eventServices']:
                serviceId = service['serviceId']
                if serviceId in serviceGroupServiceIds:
                    if serviceId in services.keys():
                        services[serviceId] += 1
                    else:
                        services[serviceId] = 1

            return services
        else:
            logging.warning('Illegal combination of kwargs - check documentation either')

    def set_event_services_counts_ajax(self, eventId, serviceId, servicesCount):
        """
        update the number of services currently set for one event specific id

        :param eventId: id number of the calendar event
        :type eventId: int
        :param serviceId: id number of the service type to be filtered for
        :type serviceId: int
        :param servicesCount: number of services of the specified type to be planned
        :type servicesCount: int
        :return: successful execution
        :rtype: bool
        """

        url = self.domain + '/index.php'
        headers = {
            'accept': 'application/json'
        }
        params = {'q': 'churchservice/ajax'}

        # restore other ServiceGroup assignments required for request form data

        services = self.get_services(returnAsDict=True)
        serviceGroupId = services[serviceId]['serviceGroupId']
        servicesOfServiceGroup = self.get_event_services_counts_ajax(eventId, serviceGroupId=serviceGroupId)
        # set new assignment
        servicesOfServiceGroup[serviceId] = servicesCount

        # Generate form specific data
        item_id = 0
        data = {
            'id': eventId,
            'func': 'addOrRemoveServiceToEvent'
        }
        for serviceIdRow, serviceCount in servicesOfServiceGroup.items():
            data['col{}'.format(item_id)] = serviceIdRow
            if serviceCount > 0:
                data['val{}'.format(item_id)] = 'checked'
            data['count{}'.format(item_id)] = serviceCount
            item_id += 1

        response = self.session.post(url=url, headers=headers, params=params, data=data)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_success = response_content['status'] == 'success'

            number_match = self.get_event_services_counts_ajax(eventId, serviceId=serviceId)[serviceId] == servicesCount
            if number_match and response_success:
                return True
            else:
                logging.warning("Request was successful but serviceId {} not changed to count {} "
                                .format(serviceId, servicesCount))
                return False
        else:
            logging.info("set_event_services_counts_ajax not successful: {}".format(response.status_code))
            return False

    def get_event_admins_ajax(self, eventId):
        """
        get the admin id list of an event using legacy AJAX API
        :param eventId: number of the event to be changed
        :type eventId: int
        :return:
        """

        event_data = self.get_AllEventData_ajax(eventId)
        if event_data is not None:
            if 'admin' in event_data.keys():
                admin_ids = [int(id) for id in event_data['admin'].split(',')]
            else:
                admin_ids = []
            return admin_ids
        else:
            logging.info('No admins found because event not found')
            return []

    def set_event_admins_ajax(self, eventId, admin_ids):
        """
        set the admin id list of an event using legacy AJAX API
        :param eventId: number of the event to be changed
        :type eventId: int
        :param admin_ids: list of admin user ids to be set as admin for event
        :type admin_ids: list
        :return:
        """

        url = self.domain + '/index.php'
        headers = {
            'accept': 'application/json'
        }
        params = {'q': 'churchservice/ajax'}

        data = {
            'id': eventId,
            'admin': ", ".join([str(id) for id in admin_ids]),
            'func': 'updateEventInfo'
        }
        response = self.session.post(url=url, headers=headers, params=params, data=data)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['status'] == 'success'
            logging.debug("Setting Admin IDs {} for event {} success".format(admin_ids, eventId))

            return response_data
        else:
            logging.info(
                "Setting Admin IDs {} for event {} failed with : {}".format(admin_ids, eventId, response.status_code))
            return False

    def get_event_agenda(self, eventId):
        """
        Retrieve agenda for event by ID from ChurchTools
        :param eventId: number of the event
        :type eventId: int
        :return:
        """
        url = self.domain + '/api/events/{}/agenda'.format(eventId)
        headers = {
            'accept': 'application/json'
        }
        response = self.session.get(url=url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['data'].copy()
            logging.debug("Agenda load successful {}".format(response_content))

            return response_data
        else:
            logging.info("Event requested that does not have an agenda with status: {}".format(response.status_code))
            return None

    def export_event_agenda(self, target_format, target_path='./downloads', **kwargs):
        """
        Exports the agenda as zip file for imports in presenter-programs
        :param target_format: fileformat or name of presentation software which should be supported.
            Supported formats are 'SONG_BEAMER', 'PRO_PRESENTER6' and 'PRO_PRESENTER7'
        :param target_path: Filepath of the file which should be exported (including filename)
        :param kwargs: additional keywords as listed below
        :key eventId: event id to check for agenda id should be exported
        :key agendaId: agenda id of the agenda which should be exported
            DO NOT combine with eventId because it will be overwritten!
        :key append_arrangement: if True, the name of the arrangement will be included within the agenda caption
        :key export_Songs: if True, the songfiles will be in the folder "Songs" within the zip file
        :key with_category: has no effect when exported in target format 'SONG_BEAMER'
        :return: bool if success
        """
        if 'eventId' in kwargs.keys():
            if 'agendaId' in kwargs.keys():
                logging.warning('Invalid use of params - can not combine eventId and agendaId!')
            else:
                agenda = self.get_event_agenda(eventId=kwargs['eventId'])
                agendaId = agenda['id']
        elif 'agendaId' in kwargs.keys():
            agendaId = kwargs['agendaId']
        else:
            logging.warning('Missing event or agendaId')
            return False

        # note: target path can be either a zip-file defined before function call or just a folder
        is_zip = target_path.lower().endswith('.zip')
        if not is_zip:
            folder_exists = os.path.isdir(target_path)
            # If folder doesn't exist, then create it.
            if not folder_exists:
                os.makedirs(target_path)
                logging.debug("created folder : ", target_path)

            if 'eventId' in kwargs.keys():
                new_file_name = '{}_{}.zip'.format(agenda['name'], target_format)
            else:
                new_file_name = '{}_agendaId_{}.zip'.format(target_format, agendaId)

            target_path = os.sep.join([target_path, new_file_name])

        url = '{}/api/agendas/{}/export'.format(self.domain, agendaId)
        # NOTE the stream=True parameter below
        params = {
            'target': target_format
        }
        json_data = {}
        # The following 3 parameter 'appendArrangement', 'exportSongs' and 'withCategory' are mandatory from the churchtools API side:
        if 'append_arrangement' in kwargs.keys():
            json_data['appendArrangement'] = kwargs['append_arrangement']
        else:
            json_data['appendArrangement'] = True

        if 'export_songs' in kwargs.keys():
            json_data['exportSongs'] = kwargs['export_songs']
        else:
            json_data['exportSongs'] = True

        if 'with_category' in kwargs.keys():
            json_data['withCategory'] = kwargs['with_category']
        else:
            json_data['withCategory'] = True

        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }

        response = self.session.post(url=url, params=params, headers=headers, json=json_data)
        result_ok = False
        if response.status_code == 200:
            response_content = json.loads(response.content)
            agenda_data = response_content['data'].copy()
            logging.debug("Agenda package found {}".format(response_content))
            result_ok = self.file_download_from_url('{}/{}'.format(self.domain, agenda_data['url']), target_path)
            if result_ok:
                logging.debug('download finished')
        else:
            logging.warning("export of event_agenda failed: {}".format(response.status_code))

        return result_ok

    def get_event_masterdata(self, **kwargs):
        """
        Function to get the Masterdata of the event module
        This information is required to map some IDs to specific items
        :param kwargs: optional keywords as listed below
        :keyword type: str with name of the masterdata type (not datatype) common types are 'absenceReasons', 'songCategories', 'services', 'serviceGroups'
        :keyword returnAsDict: if the list with one type should be returned as dict by ID
        :return: list of masterdata items, if multiple types list of lists (by type)
        """
        url = self.domain + '/api/event/masterdata'

        headers = {
            'accept': 'application/json'
        }
        response = self.session.get(url=url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['data'].copy()

            if 'type' in kwargs:
                response_data = response_data[kwargs['type']]
                if 'returnAsDict' in kwargs.keys():
                    if kwargs['returnAsDict']:
                        response_data2 = response_data.copy()
                        response_data = {item['id']: item for item in response_data2}
            logging.debug("Event Masterdata load successful {}".format(response_data))

            return response_data
        else:
            logging.info("Event Masterdata requested failed: {}".format(response.status_code))
            return None

    def get_services(self, **kwargs):
        """
        Function to get list of all or a single services configuration item from CT
        :param kwargs: optional keywords as listed
        :keyword serviceId: id of a single item for filter
        :keyword returnAsDict: true if should return a dict instead of list (not combineable if serviceId)
        :return:
        """
        url = self.domain + '/api/services'
        if 'serviceId' in kwargs.keys():
            url += '/{}'.format(kwargs['serviceId'])

        headers = {
            'accept': 'application/json'
        }
        response = self.session.get(url=url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['data'].copy()

            if 'returnAsDict' in kwargs and not 'serviceId' in kwargs:
                if kwargs['returnAsDict']:
                    result = {}
                    for item in response_data:
                        result[item['id']] = item
                    response_data = result

            logging.debug("Services load successful {}".format(response_data))
            return response_data
        else:
            logging.info("Services requested failed: {}".format(response.status_code))
            return None

    def get_tags(self, type='songs'):
        """
        Retrieve a list of all available tags of a specific domain type from ChurchTools
        Purpose: be able to find out tag-ids of all available tags for filtering by tag

        :param type: 'songs' (default) or 'persons'
        :return: list of dicts describing each tag. Each contains keys 'id' and 'name'
        """

        url = self.domain + '/api/tags'
        headers = {
            'accept': 'application/json'
        }
        params = {
            'type': type,
        }
        response = self.session.get(url=url, params=params, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content['data'].copy()
            logging.debug("SongTags load successful {}".format(response_content))

            return response_content['data']
        else:
            logging.warning("Something went wrong fetching Song-tags: {}".format(response.status_code))

    def file_download(self, filename: str, domain_type, domain_identifier, path_for_download='./downloads'):
        """
        Retrieves file from ChurchTools for specific filename, domain_type and domain_identifier from churchtools
        :param filename:
        :param domain_type: Currently supported are 'avatar', 'groupimage', 'logo', 'attatchments', 'html_template', 'service', 'song_arrangement', 'importtable', 'person', 'familyavatar', 'wiki_.?'.
        :param domain_identifier = Id of Arrangement (in case of songs) This information can be checked for example by calling get_songs()
        :param path_for_download: local path as target for the download - will be created if not exists
        :return: bool if success
        """
        StateOK = False
        CHECK_FOLDER = os.path.isdir(path_for_download)

        # If folder doesn't exist, then create it.
        if not CHECK_FOLDER:
            os.makedirs(path_for_download)
            print("created folder : ", path_for_download)

        url = '{}/api/files/{}/{}'.format(self.domain, domain_type, domain_identifier)

        response = self.session.get(url=url)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            arrangement_files = response_content['data'].copy()
            logging.debug("SongArrangement-Files load successful {}".format(response_content))
            file_found = False

            for file in arrangement_files:
                filenameoriginal = str(file['name'])
                if filenameoriginal == filename:
                    file_found = True
                    break

            if file_found:
                logging.debug("Found File: {}".format(filename))
                # Build path OS independent
                fileUrl = str(file['fileUrl'])
                path_file = os.sep.join([path_for_download, filename])
                StateOK = self.file_download_from_url(fileUrl, path_file)
            else:
                logging.warning("File {} does not exist".format(filename))

            return StateOK
        else:
            logging.warning("Something went wrong fetching SongArrangement-Files: {}".format(response.status_code))

    def file_download_from_url(self, file_url: str, target_path: str):
        """
        Retrieves file from ChurchTools for specific file_url from churchtools
        This function is used by file_download(...)
        :param file_url: Example -> file_url=https://lgv-oe.church.tools/?q=public/filedownload&id=631&filename=738db42141baec592aa2f523169af772fd02c1d21f5acaaf0601678962d06a00
                Pay Attention: this file-url consists of a specific / random filename which was created by churchtools
        :param target_path: directory to drop the download into (must exist first)
        :return:
        """
        # NOTE the stream=True parameter below
        with self.session.get(url=file_url, stream=True) as r:
            if r.status_code == 200:
                with open(target_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        # If you have chunk encoded response uncomment if
                        # and set chunk_size parameter to None.
                        # if chunk:
                        f.write(chunk)
                logging.debug("Download of {} successful".format(file_url))
                return True
            else:
                logging.warning("Something went wrong during file_download: {}".format(r.status_code))
                return False