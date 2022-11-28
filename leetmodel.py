import requests
from requests import Session
from config import us
import json


class leetmodel:
    def __init__(self, un, pw, resolve=us):
        self.session = Session()
        self.api = resolve
        resp = self.session.get(self.api["login"], headers={
            "X-Requested-With": 'XMLHttpRequest',
            "X-CSRFToken": ""
        })

        self.uname = un

        self.tokens = {"csrf": resp.cookies.get_dict()['csrftoken']}
        self.tokens["LEETCODE_SESSION"] = "abcd"

        hd = self.get_headers(self.api["login"])
        payload = {"csrfmiddlewaretoken": self.tokens["csrf"], "login": un, "password": pw}

        resp2 = self.session.post(self.api["login"], headers=hd, data=payload)
        # TODO fix the recaptcha error; potentially using
        #  https://github.com/skygragon/leetcode-cli/blob/5245886992ceb64bfb322256b2bdc24184b36d76/lib/plugins/leetcode.js#L464
        print("graphql Login response: ", resp2)
        # self.tokens["session"] = resp2.cookies.get_dict()["LEETCODE_SESSION"]

    def get_headers(self, referer=None):
        if referer == None:
            referer = self.api["base"]

        hd = {'User-Agent': 'Mozilla/5.0',
              "X-Requested-With": 'XMLHttpRequest', 'Referer': referer,
              "Cookie": f"LEETCODE_SESSION=abcd;csrftoken={self.tokens['csrf']}; _ga=GA1.2.410099775.1668743041; _gid=GA1.2.1375712340.1668743041; _gat=1; gr_user_id=962887ae-3607-42c6-bbc3-838da57a4f05; 87b5a3c3f1a55520_gr_session_id=c5ad8b1e-7dd4-4d39-a92e-6a3eb186f13d; 87b5a3c3f1a55520_gr_session_id_c5ad8b1e-7dd4-4d39-a92e-6a3eb186f13d=true"}

        if "csrf" in self.tokens:
            hd["X-CSRFToken"] = self.tokens["csrf"]

        if "session" in self.tokens:
            hd["Cookie"] = "LEETCODE_SESSION=%s;csrftoken=%s;" % (self.tokens["session"], self.tokens["csrf"])

        return hd

    """
    Get up to 20 recent submissions
    """

    def get_recent_submissions(self, user):
        op = {"operationName": "getRecentSubmissionList",
              "variables": json.dumps({"username": user}),
              "query": "query getRecentSubmissionList($username: String!, $limit: Int) {\n  recentSubmissionList("
                       "username: $username, limit: $limit) {\n    id\n    title\n    titleSlug\n    timestamp\n    "
                       "statusDisplay\n    lang\n    __typename\n  }\n  languageList {\n    id\n    name\n    "
                       "verboseName\n    __typename\n  }\n}\n"}

        hd = self.get_headers(self.api["profile"](user))

        s = self.session.post(self.api["graphql"], headers=hd, data=op)

        return json.loads(s.content)["data"]["recentSubmissionList"]

    def get_question_of_the_day(self):
        op = {
              "query": "{\n  activeDailyCodingChallengeQuestion {\n    date\n    "
                       "link\n    question {\n      acRate\n      difficulty\n      freqBar\n      "
                       "frontendQuestionId: questionFrontendId\n      isFavor\n      paidOnly: isPaidOnly\n      "
                       "status\n      title\n      titleSlug\n      hasVideoSolution\n      hasSolution\n      "
                       "}\n  }\n}\n"}

        hd = self.get_headers()
        s = self.session.post(self.api["graphql"], headers=hd, data=op)

        return json.loads(s.content)["data"]['activeDailyCodingChallengeQuestion']

    def get_user_data(self, user):
        request = requests.get('http://leetcode.com/' + user + '/')
        if request.status_code != 200:
            print(user, request)
            return None

        op = {"operationName": "getUserProfile", "variables": json.dumps({"username": user}),
              "query": "query getUserProfile($username: String!) {\n  allQuestionsCount {\n    difficulty\n    "
                       "count\n    __typename\n  }\n  matchedUser(username: $username) {\n    username\n    "
                       "socialAccounts\n    githubUrl\n    contributions {\n      points\n      questionCount\n      "
                       "testcaseCount\n      __typename\n    }\n    profile {\n      realName\n      websites\n      "
                       "countryName\n      skillTags\n      company\n      school\n      starRating\n      aboutMe\n  "
                       "    userAvatar\n      reputation\n      ranking\n      __typename\n    }\n    "
                       "submissionCalendar\n    submitStats: submitStatsGlobal {\n      acSubmissionNum {\n        "
                       "difficulty\n        count\n        submissions\n        __typename\n      }\n      "
                       "totalSubmissionNum {\n        difficulty\n        count\n        submissions\n        "
                       "__typename\n      }\n      __typename\n    }\n    badges {\n      id\n      displayName\n     "
                       " icon\n      creationDate\n      __typename\n    }\n    upcomingBadges {\n      name\n      "
                       "icon\n      __typename\n    }\n    activeBadge {\n      id\n      __typename\n    }\n    "
                       "__typename\n  }\n}\n"}

        hd = self.get_headers(self.api["profile"](user))

        s = self.session.post(self.api["graphql"], headers=hd, data=op)

        return json.loads(s.content)["data"]["matchedUser"]
