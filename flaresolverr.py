import http
import logging
import uuid
import urllib.parse
import requests
import requests.cookies
from io import BytesIO


class FlareSolverrError(requests.HTTPError):
    pass


class FlareSolverr:

    def __init__(
        self,
        url: str,
        session_id=None,
        http_session=None,
        timeout: int = 120000,
    ) -> None:
        self.url: str = url
        self.timeout: int = timeout
        self.update_session_id(session_id=session_id)
        self.http_session: requests.Session = http_session or requests.Session()

    @staticmethod
    def random_session_id() -> str:
        return str(uuid.uuid4())

    def update_session_id(self, session_id=None) -> None:
        self.session_id: str = session_id or self.random_session_id()

    def get(
        self,
        url: str,
        cookies: dict = {},
        **kwargs,
    ) -> requests.Response:
        return self.request(method='GET', url=url, cookies=cookies, **kwargs)

    def post(
        self,
        url: str,
        cookies: dict = {},
        data: dict = {},
        **kwargs,
    ) -> requests.Response:
        return self.request(method='POST', url=url, cookies=cookies, data=data, **kwargs)

    def request(
        self,
        method: str,
        url: str,
        cookies: dict = {},
        data: dict = {},
        **kwargs,
    ) -> requests.Response:
        payload = {
            'cmd': f'request.{method.lower()}',
            'url': url,
            'session': self.session_id,
            'maxTimeout': self.timeout,
            **kwargs,
        }
        if cookies:
            payload['cookies'] = [{'name': k, 'value': v} for
                                  k, v in cookies.items()]
        if method == 'post' and data:
            payload['postData'] = urllib.parse.urlencode(data)
        with self.http_session.post(url=self.url, json=payload) as r:
            if (data := r.json()) and (solution := data.get('solution')) is None:
                raise FlareSolverrError(
                    data.get('error') or data.get('message'))
            # build a fake response
            resp = requests.Response()
            resp.url = url
            resp.raw = BytesIO()
            resp.status_code = solution['status']
            resp.headers.update(solution['headers'])
            resp.headers['user-agent'] = solution['userAgent']
            requests.cookies.create_cookie
            resp.cookies = requests.cookies.cookiejar_from_dict(
                {cookie['name']: cookie['value'] for cookie in solution['cookies']})
            resp._content = str(solution['response']).encode()
            return resp


class FlareSolverrSession:

    def __init__(
        self,
        url: str,
        proxy: str = None,
        **kwargs,
    ) -> None:
        self.proxy = proxy
        self.http_session = requests.Session()

        self.headers = requests.utils.CaseInsensitiveDict()
        self.cookies = {}

        self.fs = FlareSolverr(
            url=url, http_session=self.http_session, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.http_session.close()

    @staticmethod
    def require_challenge(r: requests.Response):
        return r.status_code == http.HTTPStatus.FORBIDDEN \
            and (r.text.find('Just a moment...') > 0 or
                 r.headers.get('CF-Mitigated') == 'challenge')

    def update_cf_token(
        self,
        url: str,
        method: str = 'GET',
        retries: int = 5,
    ) -> None:
        while retries > 0:
            try:
                with self.fs.request(method=method, url=url) as r:
                    self.headers.update(r.headers)
                    self.cookies.update(r.cookies.items())
                    logging.debug(f'CF-WAF-URL: {url}')
                    logging.debug(f'CF-Cookies: {dict(r.cookies.items())}')
                    logging.debug(f'User-Agent: {r.headers["User-Agent"]}')
                    return
            except FlareSolverrError as e:
                logging.warning(
                    f'retry cf_clearance update caused by error: {e}')
                self.fs.update_session_id()  # force session id reset
                logging.debug(
                    f'reset flaresolverr session id to: {self.fs.session_id}')
            finally:
                retries -= 1
        raise FlareSolverrError(
            f'max CF challenge retries exceeded with url: {url}')

    def get(
        self,
        url: str,
        *args,
        **kwargs,
    ) -> requests.Response:
        return self.request(method='GET', url=url, *args, **kwargs)

    def post(
        self,
        url: str,
        *args,
        **kwargs,
    ) -> requests.Response:
        return self.request(method='POST', url=url, *args, **kwargs)

    def request(
        self,
        method: str,
        url: str,
        headers: dict = {},
        cookies: dict = {},
        *args,
        **kwargs,
    ):
        retries = 3
        while retries > 0:

            headers.update(self.headers)
            cookies.update(self.cookies)

            proxies = {
                "http": self.proxy,
                "https": self.proxy,
            } if self.proxy else None

            with self.http_session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    cookies=cookies,
                    proxies=proxies,
                    *args, **kwargs) as r:

                if not self.require_challenge(r):
                    return r
                self.update_cf_token(url=url)

            retries -= 1

        raise FlareSolverrError(
            f'CF challenge bypass error with url: {url}')
