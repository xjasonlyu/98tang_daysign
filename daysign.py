import os
import re
import json
import random
import uncurl
import requests
from bs4 import BeautifulSoup

SEHUATANG_HOST = 'www.sehuatang.net'
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'


def daysign(cookies: dict) -> bool:

    with requests.Session() as session:

        def _request(method, url, *args, **kwargs):
            with session.request(method=method, url=url, cookies=cookies,
                                 headers={
                                     'user-agent': DEFAULT_USER_AGENT,
                                     'x-requested-with': 'XMLHttpRequest',
                                     'accept': '*/*',
                                     'sec-ch-ua-mobile': '?0',
                                     'sec-ch-ua-platform': 'macOS',
                                     'sec-fetch-site': 'same-origin',
                                     'sec-fetch-mode': 'cors',
                                     'sec-fetch-dest': 'empty',
                                     'referer': f'https://{SEHUATANG_HOST}/plugin.php?id=dd_sign&mod=sign',
                                     'accept-language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                                 }, *args, **kwargs) as r:
                r.raise_for_status()
                return r

        with _request(method='get', url=f'https://{SEHUATANG_HOST}/plugin.php?id=dd_sign&mod=sign') as r:
            id_hash_rsl = re.findall(
                r"updatesecqaa\('(.*?)'", r.text, re.MULTILINE | re.IGNORECASE)
            id_hash = id_hash_rsl[0] if id_hash_rsl else 'qS0'  # default value

            soup = BeautifulSoup(r.text, 'html.parser')
            formhash = soup.find('input', {'name': 'formhash'})['value']
            signtoken = soup.find('input', {'name': 'signtoken'})['value']
            action = soup.find('form', {'name': 'login'})['action']

        # GET: https://www.sehuatang.net/misc.php?mod=secqaa&action=update&idhash=qS0&0.2010053552105764
        with _request(method='get', url=f'https://{SEHUATANG_HOST}/misc.php?mod=secqaa&action=update&idhash={id_hash}&{round(random.random(), 16)}') as r:
            qes_rsl = re.findall(r"'(.*?) = \?'", r.text,
                                 re.MULTILINE | re.IGNORECASE)

            if not qes_rsl or not qes_rsl[0]:
                raise Exception('invalid or empty question!')
            qes = qes_rsl[0]
            ans = eval(qes)
            assert type(ans) == int

        # POST: https://www.sehuatang.net/plugin.php?id=dd_sign&mod=sign&signsubmit=yes&signhash=LMAB9&inajax=1
        with _request(method='post', url=f'https://{SEHUATANG_HOST}/{action.lstrip("/")}&inajax=1',
                      data={'formhash': formhash,
                            'signtoken': signtoken,
                            'secqaahash': id_hash,
                            'secanswer': ans}) as r:
            return r.text


def retrieve_cookies_from_curl(env: str) -> dict:
    cURL = os.getenv(env, '').replace('\\', '')
    return uncurl.parse_context(curl_command=cURL).cookies


def telegram_send_message(text: str, chat_id: str, token: str, silent: bool = False):
    with requests.post(url=f'https://api.telegram.org/bot{token}/sendMessage',
                       headers={'Content-Type': 'application/json'},
                       data=json.dumps({
                           'chat_id': chat_id,
                           'text': text,
                           'parse_mode': 'HTML',
                           'disable_notification': silent,
                       })) as r:
        r.raise_for_status()
        return r.json()


def main():
    cookies = retrieve_cookies_from_curl('CURL')
    raw_html = daysign(cookies=cookies)

    try:
        if '签到成功' in raw_html:
            message_text = re.findall(
                r"'(签到成功.+?)'", raw_html, re.MULTILINE)[0]
        elif '已经签到' in raw_html:
            message_text = re.findall(
                r"'(已经签到.+?)'", raw_html, re.MULTILINE)[0]
        elif '需要先登录' in raw_html:
            message_text = f'<b>98堂 签到异常</b>\n\nCookie无效或已过期，请重新获取。'
        else:
            message_text = raw_html
    except IndexError:
        message_text = f'<b>98堂 签到异常</b>\n\n正则匹配错误\n--------------------\n{raw_html}'
    except Exception as e:
        message_text = f'<b>98堂 签到异常</b>\n\n错误原因：{e}\n--------------------\n{raw_html}'

    # log to output
    print(message_text)

    # telegram notify
    chat_id = os.getenv('CHAT_ID')
    bot_token = os.getenv('BOT_TOKEN')
    if chat_id and bot_token:
        telegram_send_message(message_text, chat_id, bot_token, silent=(
            True if '签到成功' in message_text else False))


if __name__ == '__main__':
    main()
