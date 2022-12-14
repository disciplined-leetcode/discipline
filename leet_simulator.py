import json

import requests

from cookies_model import CookieModel

cookie_model = CookieModel()
# if file exists, read cookies from file
try:
    with open("cookies.txt", "r") as f:
        cookie_model.set(f.read())
except FileNotFoundError:
    print("No cookies.txt file found, please set using /admin_set_cookies")


__all__ = ["get_submission_details", "set_cookies"]

headers = {
    'authority': 'leetcode.com',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
              'application/signed-exchange;v=b3;q=0.9',
    'accept-language': 'zh-CN,zh;q=0.9',
    'cache-control': 'no-cache',
    'dnt': '1',
    'pragma': 'no-cache',
    'sec-ch-ua': '"Chromium";v="106", "Google Chrome";v="106", "Not;A=Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/106.0.0.0 Safari/537.36',
}


json_data = {"operationName": "submissionDetails",
             "query": "query submissionDetails($submissionId: Int!) {\n  submissionDetails(submissionId: "
                      "$submissionId) {\n    runtimePercentile\n    memoryPercentile\n    "
                      "code\n    lang {\n      name    }}\n}\n "
             }


def get_submission_details(submission_id):
    json_data['variables'] = json.dumps({"submissionId": submission_id})
    res = requests.post('https://leetcode.com/graphql', cookies=cookie_model.cookies, headers=headers, json=json_data).json()
    lang = res['data']['submissionDetails']['lang']['name']
    code = res['data']['submissionDetails']['code'].removesuffix('\n')
    # TODO return headers to check for rate limiting information during 429's
    return {
        'lang': lang,
        'code': code,
        'runtime': f"{(res['data']['submissionDetails']['runtimePercentile']):.2f}%",
        'memory': f"{(res['data']['submissionDetails']['memoryPercentile']):.2f}%",
    }


def set_cookies(cookies):
    status = cookie_model.set(cookies)
    with open("cookies.txt", "w") as f:
        f.write(cookies)
    return status

if __name__ == "__main__":
    print(get_submission_details(815504963))
