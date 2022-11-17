__all__ = ["CookieModel"]
import urllib.parse


class CookieModel:
    def __init__(self):
        self.cookies = {}

    def set(self, cookie_str: str) -> bool:
        try:
            # {key: value for key, value in [e.split("=") for e in cookie_str.split(";")]}
            self.cookies = dict(urllib.parse.parse_qsl(cookie_str, separator="; "))
            return True
        except AttributeError as e:
            return False
