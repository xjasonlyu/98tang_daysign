import http
import httpx
import logging
import time
import uuid
import urllib.parse


class FlareSolverrError(httpx.RequestError):
    pass


class FlareSolverrResponse(httpx.Response):

    def __enter__(self):
        self.read()
        return self

    def __exit__(self, *args):
        self.close()

    @classmethod
    def from_httpx_resp(cls, resp: httpx.Response):
        resp.__class__ = FlareSolverrResponse
        return resp


class FlareSolverr:

    def __init__(
        self,
        url: str,
        session_id: str = None,
        http_client: httpx.Client = None,
        timeout: int = None,
    ) -> None:
        self.url: str = url
        self.timeout: int = timeout
        self.update_session_id(session_id=session_id)
        self.http_client: httpx.Client = http_client or httpx.Client()
        self.http_client.timeout = timeout

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
    ) -> FlareSolverrResponse:
        return self.request(method='GET', url=url, cookies=cookies, **kwargs)

    def post(
        self,
        url: str,
        cookies: dict = {},
        data: dict = {},
        **kwargs,
    ) -> FlareSolverrResponse:
        return self.request(method='POST', url=url, cookies=cookies, data=data, **kwargs)

    def request(
        self,
        method: str,
        url: str,
        *,
        cookies: dict = {},
        data: dict = {},
        **kwargs,
    ) -> FlareSolverrResponse:
        payload = {
            'cmd': f'request.{method.lower()}',
            'url': url,
            'session': self.session_id,
            'maxTimeout': self.timeout or 120000,
            **kwargs,
        }
        if cookies:
            payload['cookies'] = [{'name': k, 'value': v} for
                                  k, v in cookies.items()]
        if method == 'post' and data:
            payload['postData'] = urllib.parse.urlencode(data)
        # make POST request
        with self.http_client.stream(method='POST', url=self.url, json=payload) as r:
            if r.read() and (data := r.json()) and (solution := data.get('solution')) is None:
                raise FlareSolverrError(
                    data.get('error') or data.get('message'))

            # build a fake response
            resp = FlareSolverrResponse(
                status_code=solution['status'],
                headers=solution['headers'],
                json=solution['response'],
                request=httpx.Request(
                    method=method.upper(),
                    url=solution['url'],
                ),
            )
            resp.headers['User-Agent'] = solution['userAgent']
            for cookie in solution['cookies']:
                resp.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie['domain'],
                )
            return resp


class FlareSolverrHTTPClient:

    HTTPX_USER_AGENT = httpx._client.USER_AGENT

    def __init__(
        self,
        url: str,
        session_id=None,
        timeout: int = 120000,
        **kwargs,
    ) -> None:

        self.fs = FlareSolverr(
            url=url,
            session_id=session_id,
            timeout=timeout,
        )
        self.http_client = httpx.Client(
            timeout=timeout, **kwargs,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.http_client.close()

    @property
    def cookies(self) -> httpx.Cookies:
        return self.http_client.cookies

    @staticmethod
    def require_challenge(r: httpx.Response) -> bool:
        return r.status_code == http.HTTPStatus.FORBIDDEN \
            and (r.text.find('Just a moment...') > 0 or
                 r.headers.get('CF-Mitigated') == 'challenge')

    def preprocess_headers(self, headers: dict) -> httpx.Headers:
        headers = httpx.Headers(headers=headers)
        if self.http_client.headers.get(
                'User-Agent', self.HTTPX_USER_AGENT) != self.HTTPX_USER_AGENT:
            headers.pop('User-Agent', None)
        return headers

    def update_cf_token(
        self,
        url: str,
        method: str = 'GET',
        retries: int = 5,
    ) -> None:
        while retries > 0:
            try:
                with self.fs.request(method=method, url=url) as r:
                    for cookie in r.cookies.jar:
                        self.http_client.cookies.set(
                            name=cookie.name,
                            value=cookie.value,
                            domain=cookie.domain,
                        )
                    self.http_client.headers['User-Agent'] = r.headers['User-Agent']
                    logging.info(f'CF-WAF-URL: {url}')
                    logging.info(f'CF-Cookies: {dict(r.cookies.items())}')
                    logging.info(f'User-Agent: {r.headers["User-Agent"]}')
                    return
            except FlareSolverrError as e:
                logging.warning(
                    f'Retry cf_clearance update after 10 seconds caused by error: {e}')
                time.sleep(10)  # wait for 10 seconds
                self.fs.update_session_id()  # force session id reset
                logging.info(
                    f'Reset flaresolverr session id to: {self.fs.session_id}')
            finally:
                retries -= 1
        raise FlareSolverrError(
            f'max CF challenge retries exceeded with URL: {url}')

    def get(
        self,
        url: str,
        **kwargs,
    ) -> FlareSolverrResponse:
        return self.request(method='GET', url=url, **kwargs)

    def post(
        self,
        url: str,
        **kwargs,
    ) -> FlareSolverrResponse:
        return self.request(method='POST', url=url, **kwargs)

    def request(
        self,
        url: str,
        **kwargs,
    ) -> FlareSolverrResponse:
        with self.stream(url=url, **kwargs) as r:
            return r

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict = {},
        **kwargs,
    ) -> FlareSolverrResponse:

        retries = 3
        while retries > 0:

            r = self.http_client.request(
                method=method,
                url=url,
                headers=self.preprocess_headers(headers=headers),
                **kwargs)

            if not self.require_challenge(r):
                return FlareSolverrResponse.from_httpx_resp(r)

            logging.info(f'Challenge detected with URL: {url}')
            self.update_cf_token(url=url)

            retries -= 1

        raise FlareSolverrError(
            f'CF challenge bypass error with URL: {url}')
