import json
import logging
from typing import Optional

import requests

from churchtools_api.calendar import ChurchToolsApiCalendar
from churchtools_api.events import ChurchToolsApiEvents
from churchtools_api.files import ChurchToolsApiFiles
from churchtools_api.groups import ChurchToolsApiGroups
from churchtools_api.persons import ChurchToolsApiPersons
from churchtools_api.resources import ChurchToolsApiResources
from churchtools_api.songs import ChurchToolsApiSongs

logger = logging.getLogger(__name__)


class ChurchToolsApi(
    ChurchToolsApiPersons,
    ChurchToolsApiEvents,
    ChurchToolsApiGroups,
    ChurchToolsApiSongs,
    ChurchToolsApiFiles,
    ChurchToolsApiCalendar,
    ChurchToolsApiResources,
):
    """Main class used to combine all api functions.

    Args:
        ChurchToolsApiPersons: all functions used for persons
        ChurchToolsApiEvents: all functions used for events
        ChurchToolsApiGroups: all functions used for groups
        ChurchToolsApiSongs: all functions used for songs
        ChurchToolsApiFiles: all functions used for files
        ChurchToolsApiCalendars: all functions used for calendars
        ChurchToolsApiResources: all functions used for resources
    """

    def __init__(
        self,
        domain: str,
        ct_token: Optional[str] = None,
        ct_user: Optional[str] = None,
        ct_password: Optional[str] = None,
    ) -> None:
        """Setup of a ChurchToolsApi object for the specified ct_domain using a token login.

        Arguments:
            domain: including https:// ending on e.g. .de
            ct_token: direct access using a user token
            ct_user: indirect login using user and password combination
            ct_password: indirect login using user and password combination

        """
        super().__init__()
        self.session = None
        self.domain = domain
        self.ajax_song_last_update = None
        self.ajax_song_cache = []

        if ct_token is not None:
            self.login_ct_rest_api(ct_token=ct_token)
        elif ct_user is not None and ct_password is not None:
            self.login_ct_rest_api(ct_user=ct_user, ct_password=ct_password)

        logger.debug("ChurchToolsApi init finished")

    def login_ct_rest_api(self, **kwargs):
        """Authorization: Login<token>
        If you want to authorize a request, you need to provide a Login Token as
        Authorization header in the format {Authorization: Login<token>}
        Login Tokens are generated in "Berechtigungen" of User Settings
        using REST API login as opposed to AJAX login will also save a cookie.

        :param kwargs: optional keyword arguments as listed
        :keyword ct_token: str : token to be used for login into CT
        :keyword ct_user: str: the username to be used in case of unknown login token
        :keyword ct_password: str: the password to be used in case of unknown login token
        :return: personId if login successful otherwise False
        :rtype: int | bool
        """
        self.session = requests.Session()

        if "ct_token" in kwargs:
            logger.info("Trying Login with token")
            url = self.domain + "/api/whoami"
            headers = {"Authorization": "Login " + kwargs["ct_token"]}
            response = self.session.get(url=url, headers=headers)

            if response.status_code == 200:
                response_content = json.loads(response.content)
                logger.info(
                    "Token Login Successful as %s",
                    response_content["data"]["email"],
                )
                self.session.headers["CSRF-Token"] = self.get_ct_csrf_token()
                return json.loads(response.content)["data"]["id"]
            logger.warning(
                "Token Login failed with %s",
                response.content.decode(),
            )
            return False

        if "ct_user" in kwargs and "ct_password" in kwargs:
            logger.info("Trying Login with Username/Password")
            url = self.domain + "/api/login"
            data = {"username": kwargs["ct_user"], "password": kwargs["ct_password"]}
            response = self.session.post(url=url, data=data)

            if response.status_code == 200:
                response_content = json.loads(response.content)
                person = self.who_am_i()
                logger.info("User/Password Login Successful as %s", person["email"])
                return person["id"]
            logger.warning(
                "User/Password Login failed with %s",
                response.content.decode(),
            )
            return False
        return None

    def get_ct_csrf_token(self):
        """Requests CSRF Token https://hilfe.church.tools/wiki/0/API-CSRF
        Storing and transmitting CSRF token in headers is required for all legacy AJAX API calls unless disabled by admin
        Therefore it is executed with each new login.

        :return: token
        :rtype: str
        """
        url = self.domain + "/api/csrftoken"
        response = self.session.get(url=url)
        if response.status_code == 200:
            csrf_token = json.loads(response.content)["data"]
            logger.debug("CSRF Token erfolgreich abgerufen %s", csrf_token)
            return csrf_token
        logger.warning(
            "CSRF Token not updated because of Response %s",
            response.content.decode(),
        )
        return None

    def who_am_i(self):
        """Simple function which returns the user information for the authorized user
        :return: CT user dict if found or bool
        :rtype: dict | bool.
        """
        url = self.domain + "/api/whoami"
        response = self.session.get(url=url)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            if "email" in response_content["data"]:
                logger.info("Who am I as %s", response_content["data"]["email"])
                return response_content["data"]
            logger.warning("User might not be logged in? %s", response_content["data"])
            return False
        logger.warning("Checking who am i failed with %s", response.status_code)
        return False

    def check_connection_ajax(self) -> bool:
        """Checks whether a successful connection with the given token can be initiated using the legacy AJAX API
        This requires a CSRF token to be set in headers
        :return: if successful.
        """
        url = self.domain + "/?q=churchservice/ajax&func=getAllFacts"
        headers = {"accept": "application/json"}
        response = self.session.post(url=url, headers=headers)
        if response.status_code == 200:
            logger.debug("Response AJAX Connection successful")
            return True
        logger.debug(
            "Response AJAX Connection failed with %s",
            json.load(response.content),
        )
        return False

    def get_global_permissions(self) -> dict:
        """Get global permissions of the current user
        :return: dict with module names which contain dicts with individual permissions items.
        """
        url = self.domain + "/api/permissions/global"
        headers = {"accept": "application/json"}
        response = self.session.get(url=url, headers=headers)
        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content["data"].copy()
            logger.debug(
                "First response of Global Permissions successful %s", response_content
            )

            return response_data
        logger.warning(
            "%s Something went wrong fetching global permissions: %s",
            response.status_code,
            response_content,
        )
        return None

    def get_services(self, **kwargs):
        """Function to get list of all or a single services configuration item from CT
        :param kwargs: optional keywords as listed
        :keyword serviceId: id of a single item for filter
        :keyword returnAsDict: true if should return a dict instead of list (not combineable if serviceId)
        :return: list of services
        :rtype: list[dict].
        """
        url = self.domain + "/api/services"
        if "serviceId" in kwargs:
            url += "/{}".format(kwargs["serviceId"])

        headers = {"accept": "application/json"}
        response = self.session.get(url=url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content["data"].copy()

            if kwargs.get("returnAsDict", False) and "serviceId" not in kwargs:
                result = {}
                for item in response_data:
                    result[item["id"]] = item
                response_data = result

            logger.debug(
                "Services load successful with %s entries",
                len(response_data),
            )
            return response_data
        logger.info("Services requested failed: %s", response.status_code)
        return None

    def get_tags(self, type="songs"):  # noqa: A002
        """Retrieve a list of all available tags of a specific ct_domain type from ChurchTools
        Purpose: be able to find out tag-ids of all available tags for filtering by tag.

        :param type: 'songs' (default) or 'persons'
        :type type: str
        :return: list of dicts describing each tag. Each contains keys 'id' and 'name'
        :rtype list[dict]
        """
        url = self.domain + "/api/tags"
        headers = {"accept": "application/json"}
        params = {
            "type": type,
        }
        response = self.session.get(url=url, params=params, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_content["data"].copy()
            logger.debug("SongTags load successful %s", response_content)

            return response_content["data"]
        logger.warning(
            "%s Something went wrong fetching Song-tags: %s",
            response.status_code,
            response.content,
        )
        return None

    def get_options(self) -> dict:
        """Helper function which returns all configurable option fields from CT.
        e.g. common use is sexId.

        Returns:
            dict of options - named by "name" from original list response
        """
        url = self.domain + "/api/dbfields"
        headers = {"accept": "application/json"}
        params = {
            "include[]": "options",
        }
        response = self.session.get(url=url, params=params, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content)
            response_data = response_content["data"].copy()
            logger.debug("SongTags load successful %s", response_content)
            return {item["name"]: item for item in response_data}
        logger.warning(
            "%s Something went wrong fetching Song-tags: %s",
            response.status_code,
            response.content,
        )
        return None
