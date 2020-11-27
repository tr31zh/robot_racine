from kivy.network.urlrequest import UrlRequest
from functools import partial
from time import sleep
import urllib


received_data = False


def success(*args):
    global received_data
    print(args)
    received_data = True


def failure(*args):
    print(args)


def main():
    command = "start"
    print("Sending request")
    params = urllib.parse.urlencode({"@number": 12524, "@type": "issue", "@action": "show"})
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}

    r = UrlRequest(
        url=f"http://192.168.0.23/{command}",
        req_headers=headers,
        on_success=partial(success, command),
        on_failure=partial(failure, command),
    )
    print(str(r))
    sleep(1)


if __name__ == "__main__":
    main()