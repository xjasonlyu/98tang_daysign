import os
import re
import time
import httpx
import traceback
import random
from contextlib import contextmanager
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET
from flaresolverr import FlareSolverrHTTPClient

SEHUATANG_HOST = 'www.sehuatang.net'
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'

FID = 103  # 高清中文字幕

AUTO_REPLIES = (
    '感谢楼主分享好片',
    '感谢分享！！',
    '谢谢分享！',
    '感谢分享感谢分享',
    '必需支持',
    '简直太爽了',
    '感谢分享啊',
    '封面还不错',
    '有点意思啊',
    '封面还不错，支持一波',
    '真不错啊',
    '不错不错',
    '这身材可以呀',
    '终于等到你',
    '不错。。！',
    '謝謝辛苦分享',
    '赏心悦目',
    '快乐无限~~',
    '這怎麼受的了啊',
    '谁也挡不住！',
    '感謝分享',
    '分享支持。',
    '这谁顶得住啊',
    '这是要精J人亡啊！',
    '饰演很赞',
    '這系列真有戲',
    '感谢大佬分享',
    '看着不错',
    '感谢老板分享',
    '可以看看',
    '谢谢分享！！！',
    '真是骚气十足',
    '给我看硬了！',
    '这个眼神谁顶得住。',
    '妙不可言',
    '看硬了，确实不错。',

)


def daysign(
    cookies: dict,
    flaresolverr_url: str = None,
    flaresolverr_proxy: str = None,
) -> bool:

    with (FlareSolverrHTTPClient(url=flaresolverr_url,
                                 proxy=flaresolverr_proxy,
                                 cookies=cookies,
                                 http2=True)
          if flaresolverr_url else httpx.Client(cookies=cookies, http2=True)) as client:

        @contextmanager
        def _request(method, url, *args, **kwargs):
            r = client.request(method=method, url=url,
                               headers={
                                   'user-agent': DEFAULT_USER_AGENT,
                                   'x-requested-with': 'XMLHttpRequest',
                                   'dnt': '1',
                                   'accept': '*/*',
                                   'sec-ch-ua-mobile': '?0',
                                   'sec-ch-ua-platform': 'macOS',
                                   'sec-fetch-site': 'same-origin',
                                   'sec-fetch-mode': 'cors',
                                   'sec-fetch-dest': 'empty',
                                   'referer': f'https://{SEHUATANG_HOST}/plugin.php?id=dd_sign&mod=sign',
                                   'accept-language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                               }, *args, **kwargs)
            try:
                r.raise_for_status()
                yield r
            finally:
                r.close()

        age_confirmed = False
        age_retry_cnt = 3
        while not age_confirmed and age_retry_cnt > 0:
            with _request(method='get', url=f'https://{SEHUATANG_HOST}/') as r:
                if (v := re.findall(r"safeid='(\w+)'",
                                    r.text, re.MULTILINE | re.IGNORECASE)) and (safeid := v[0]):
                    print(f'set age confirm cookie: _safe={safeid}')
                    client.cookies.set(name='_safe', value=safeid)
                else:
                    age_confirmed = True
                age_retry_cnt -= 1

        if not age_confirmed:
            raise Exception('failed to pass age confirmation')

        with _request(method='get', url=f'https://{SEHUATANG_HOST}/forum.php?mod=forumdisplay&fid={FID}') as r:
            tids = re.findall(r"normalthread_(\d+)", r.text,
                              re.MULTILINE | re.IGNORECASE)
            tid = random.choice(tids)
            print(f'choose tid = {tid} to comment')

        with _request(method='get', url=f'https://{SEHUATANG_HOST}/forum.php?mod=viewthread&tid={tid}&extra=page%3D1') as r:
            soup = BeautifulSoup(r.text, 'html.parser')
            formhash = soup.find('input', {'name': 'formhash'})['value']

        message = random.choice(AUTO_REPLIES)

        with _request(method='post', url=f'https://{SEHUATANG_HOST}/forum.php?mod=post&action=reply&fid={FID}&tid={tid}&extra=page%3D1&replysubmit=yes&infloat=yes&handlekey=fastpost&inajax=1',
                      data={
                          'file': '',
                          'message': message,
                          'posttime': int(time.time()),
                          'formhash': formhash,
                          'usesig': '',
                          'subject': '',
                      }) as r:
            print(f'comment to: tid = {tid}, message = {message}')

        with _request(method='get', url=f'https://{SEHUATANG_HOST}/plugin.php?id=dd_sign&mod=sign') as r:
            # id_hash_rsl = re.findall(
            #     r"updatesecqaa\('(.*?)'", r.text, re.MULTILINE | re.IGNORECASE)
            # id_hash = id_hash_rsl[0] if id_hash_rsl else 'qS0'  # default value

            # soup = BeautifulSoup(r.text, 'html.parser')
            # formhash = soup.find('input', {'name': 'formhash'})['value']
            # signtoken = soup.find('input', {'name': 'signtoken'})['value']
            # action = soup.find('form', {'name': 'login'})['action']
            pass

        with _request(method='get', url=f'https://{SEHUATANG_HOST}/plugin.php?id=dd_sign&ac=sign&infloat=yes&handlekey=pc_click_ddsign&inajax=1&ajaxtarget=fwin_content_pc_click_ddsign') as r:
            soup = BeautifulSoup(r.text, 'xml')
            html = soup.find('root').string
            # extract argument values from signform
            root = BeautifulSoup(html, 'html.parser')
            id_hash = (root.find('span', id=re.compile(r'^secqaa_'))
                       ['id']).removeprefix('secqaa_')
            formhash = root.find('input', {'name': 'formhash'})['value']
            signtoken = root.find('input', {'name': 'signtoken'})['value']
            action = root.find('form', {'name': 'login'})['action']
            print(
                f'signform values: id_hash={id_hash}, formhash={formhash}, signtoken={signtoken}')
            print(f'action href: {action}')

        # GET: https://www.sehuatang.net/misc.php?mod=secqaa&action=update&idhash=qS0&0.2010053552105764
        with _request(method='get', url=f'https://{SEHUATANG_HOST}/misc.php?mod=secqaa&action=update&idhash={id_hash}&{round(random.random(), 16)}') as r:
            qes_rsl = re.findall(r"'(.*?) = \?'", r.text,
                                 re.MULTILINE | re.IGNORECASE)

            if not qes_rsl or not qes_rsl[0]:
                raise Exception('invalid or empty question!')
            qes = qes_rsl[0]
            ans = eval(qes)
            print(f'verification question: {qes} = {ans}')
            assert type(ans) == int

        # POST: https://www.sehuatang.net/plugin.php?id=dd_sign&mod=sign&signsubmit=yes&signhash=LMAB9&inajax=1
        with _request(method='post', url=f'https://{SEHUATANG_HOST}/{action.lstrip("/")}&inajax=1',
                      data={'formhash': formhash,
                            'signtoken': signtoken,
                            'secqaahash': id_hash,
                            'secanswer': ans}) as r:
            return r.text


def retrieve_cookies_from_curl(env: str) -> dict:
    cURL = os.getenv(env, '').replace('\\', ' ')
    try:
        import uncurl
        return uncurl.parse_context(curl_command=cURL).cookies
    except ImportError:
        print("uncurl is required.")


def retrieve_cookies_from_fetch(env: str) -> dict:
    def parse_fetch(s: str) -> dict:
        ans = {}
        exec(s, {
            'fetch': lambda _, o: ans.update(o),
            'null': None
        })
        return ans
    cookie_str = parse_fetch(os.getenv(env))['headers']['cookie']
    return dict(s.strip().split('=', maxsplit=1) for s in cookie_str.split(';'))


def preprocess_text(text) -> str:
    if 'xml' not in text:
        return text

    try:
        root = ET.fromstring(text)
        cdata = root.text
        soup = BeautifulSoup(cdata, 'html.parser')
        for script in soup.find_all('script'):
            script.decompose()
        return soup.get_text()
    except:
        return text


def push_notification(title: str, content: str) -> None:

    def telegram_send_message(text: str, chat_id: str, token: str, silent: bool = False) -> None:
        r = httpx.post(url=f'https://api.telegram.org/bot{token}/sendMessage',
                       json={
                           'chat_id': chat_id,
                           'text': text,
                           'disable_notification': silent,
                           'disable_web_page_preview': True,
                       })
        r.raise_for_status()

    try:
        from notify import telegram_bot
        telegram_bot(title, content)
    except ImportError:
        chat_id = os.getenv('TG_USER_ID')
        bot_token = os.getenv('TG_BOT_TOKEN')
        if chat_id and bot_token:
            telegram_send_message(f'{title}\n\n{content}', chat_id, bot_token)


def main():

    raw_html = None
    cookies = {}

    if os.getenv('FETCH_98TANG'):
        cookies = retrieve_cookies_from_fetch('FETCH_98TANG')
    elif os.getenv('CURL_98TANG'):
        cookies = retrieve_cookies_from_curl('CURL_98TANG')

    try:
        raw_html = daysign(
            cookies=cookies,
            flaresolverr_url=os.getenv('FLARESOLVERR_URL'),
            flaresolverr_proxy=os.getenv('FLARESOLVERR_PROXY'),
        )

        if '签到成功' in raw_html:
            title, message_text = '98堂 每日签到', re.findall(
                r"'(签到成功.+?)'", raw_html, re.MULTILINE)[0]
        elif '已经签到' in raw_html:
            title, message_text = '98堂 每日签到', re.findall(
                r"'(已经签到.+?)'", raw_html, re.MULTILINE)[0]
        elif '需要先登录' in raw_html:
            title, message_text = '98堂 签到异常', f'Cookie无效或已过期，请重新获取'
        else:
            title, message_text = '98堂 签到异常', raw_html
    except IndexError:
        title, message_text = '98堂 签到异常', f'正则匹配错误'
    except Exception as e:
        title, message_text = '98堂 签到异常', f'错误原因：{e}'
        # log detailed error message
        traceback.print_exc()

    # process message data
    message_text = preprocess_text(message_text)

    # log to output
    print(message_text)

    # telegram notify
    push_notification(title, message_text)


if __name__ == '__main__':
    main()
