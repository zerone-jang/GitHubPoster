from collections import defaultdict

from github_poster.err import DepNotInstalledError
from github_poster.loader.base_loader import BaseLoader


class GarminLoader(BaseLoader):
    track_color = "#E17A05"
    unit = "km"

    def __init__(self, from_year, to_year, _type, **kwargs):
        super().__init__(from_year, to_year, _type)
        self.before = None
        self.after = None
        self.number_by_date_dict = defaultdict(float)
        self.garmin_user_name = kwargs.get("garmin_user_name", "")
        self.garmin_password = kwargs.get("garmin_password", "")
        self.garmin_secret_string = kwargs.get("garmin_secret_string", "")
        self.is_cn = kwargs.get("cn", False)
        self.client = None
        self.use_garth = False

    @classmethod
    def try_import_deps(cls):
        try:
            import garminconnect  # noqa: F401
        except ImportError:
            raise DepNotInstalledError(
                "Garmin dependencies are not installed, "
                "please use `pip3 install -U 'github_poster[garmin]'` to install."
            ) from None

    @classmethod
    def add_loader_arguments(cls, parser, optional):
        parser.add_argument(
            "--garmin_user_name",
            dest="garmin_user_name",
            type=str,
            required=False,
            help="The username of Garmin",
        )
        parser.add_argument(
            "--garmin_password",
            dest="garmin_password",
            type=str,
            required=False,
            help="The password of Garmin",
        )
        parser.add_argument(
            "--garmin_secret_string",
            dest="garmin_secret_string",
            type=str,
            required=False,
            help="garth token secret string (from garth.client.dumps()), "
            "avoids password login which Garmin blocks in CI",
        )

    def _get_access(self):
        if self.garmin_secret_string:
            import garth

            if self.is_cn:
                garth.configure(domain="garmin.cn")
            garth.client.loads(self.garmin_secret_string)
            if garth.client.oauth2_token.expired:
                garth.client.refresh_oauth2()
            self.client = garth.client
            self.use_garth = True
            return

        from garminconnect import Garmin

        try:
            self.client = Garmin(
                self.garmin_user_name, self.garmin_password, is_cn=self.is_cn
            )
            self.client.login()
        except Exception as e:  # try twice
            print(str(e))
            print("try login again")
            self.client = Garmin(
                self.garmin_user_name, self.garmin_password, is_cn=self.is_cn
            )
            self.client.login()

    def get_api_data(self, start=0, limit=100):
        if self.client is None:
            self._get_access()
        if self.use_garth:
            activities = self.client.connectapi(
                "/activitylist-service/activities/search/activities",
                params={"start": start, "limit": limit},
            )
        else:
            activities = self.client.get_activities(start=start, limit=limit)
        if activities:
            # maybe some other way to do this
            yield from activities
            yield from self.get_api_data(start=start + limit, limit=limit)

    def make_track_dict(self):
        for activity in self.get_api_data():
            date = activity.get("startTimeLocal", None)
            distance = activity.get("distance", 0)
            if date and distance:
                date = date[:10]
                distance = round(distance, 2)
                self.number_by_date_dict[date] += distance / 1000

    def get_all_track_data(self):
        self.make_track_dict()
        self.make_special_number()
        return self.number_by_date_dict, self.year_list
