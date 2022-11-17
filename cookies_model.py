__all__ = ["CookieModel"]


class CookieModel:
    def __init__(self):
        self.cookies = {}

    def set(self, cookie_str: str) -> bool:
        try:
            self.cookies = {
                key: value
                for key, value in [e.split("=") for e in cookie_str.split(";")]
            }
            return True
        except AttributeError as e:
            return False
