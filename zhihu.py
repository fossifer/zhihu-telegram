import aiohttp
import asyncio
import base64
import config
import execjs
import hmac
import hashlib
import json
import re
import os
import sys
import time
from typing import Union
from PIL import Image
from urllib.parse import urlencode
from utils import print_colour
from log import get_logger

class ZhihuClient(aiohttp.ClientSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        headers = {
            'Host': 'www.zhihu.com',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Connection': 'Keep-Alive',
            'Referer': 'https://www.zhihu.com/',
            'accept-encoding': 'gzip, deflate',
        }
        self._default_headers = headers
        self.username = config.username
        self.password = config.password
        self.logger = get_logger()
        self.cookie_file = config.cookie_file or '/tmp/cookies.pick'

    async def login(self, load_cookies: bool=False) -> None:
        """
        登录
        :param load_cookies: 是否加载cookie
        :return:
        """
        if load_cookies:
            self.cookie_jar.load(self.cookie_file)
            self.logger.debug(f'加载cookies从:{self.cookie_file}')
            is_succ = await self.check_login()
            if is_succ:
                print_colour('登录成功!', colour='green')
                return
            else:
                print_colour('通过缓存登录失败尝试重新登录', 'red')
                self.cookie_jar.clear()
                os.remove(self.cookie_file)

        login_data = {
            'client_id': 'c3cef7c66a1843f8b3a9e6a1e3160e20',
            'grant_type': 'password',
            'source': 'com.zhihu.web',
            'username': self.username,
            'password': self.password,
            'lang': 'en',  # en 4位验证码, cn 中文验证码
            'ref_source': 'homepage',
            'utm_source': ''
        }
        xsrf = await self._get_xsrf()
        captcha = await self._get_captcha()
        timestamp = int(time.time() * 1000)
        login_data.update({
            'captcha': captcha,
            'timestamp': timestamp,
            'signature': self._get_signature(timestamp, login_data)
        })
        headers = {
            'accept-encoding': 'gzip, deflate, br',
            'Host': 'www.zhihu.com',
            'Referer': 'https://www.zhihu.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/46.0.2486.0 Safari/537.36 Edge/13.10586',
            'content-type': 'application/x-www-form-urlencoded',
            'x-zse-83': '3_1.1',
            'x-xsrftoken': xsrf
        }
        data = self._encrypt(login_data)
        url = 'https://www.zhihu.com/api/v3/oauth/sign_in'
        async with self.post(url, data=data, headers=headers) as r:
            resp = await r.text()
            if 'error' in resp:
                print_colour(json.loads(resp)['error'], 'red')
                self.logger.debug(f"登录失败:{json.loads(resp)['error']}")
                sys.exit()
            self.logger.debug(resp)
            is_succ = await self.check_login()
            if is_succ:
                print_colour('登录成功!', colour='green')
            else:
                print_colour('登录失败!', colour='red')
                sys.exit()

    async def _get_captcha(self) -> str:
        """
        请求验证码的 API 接口，无论是否需要验证码都需要请求一次
        如果需要验证码会返回图片的 base64 编码
        根据 lang 参数匹配验证码，需要人工输入
        :param lang: 返回验证码的语言(en/cn)
        :return: 验证码的 POST 参数
        """

        url = 'https://www.zhihu.com/api/v3/oauth/captcha?lang=en'
        async with self.get(url) as r:
            resp = await r.text()
            show_captcha = re.search(r'true', resp)
        if show_captcha:
            async with self.put(url) as r:
                resp = await r.text()
            json_data = json.loads(resp)
            img_base64 = json_data['img_base64'].replace(r'\n', '')
            with open(f'./captcha.jpg', 'wb') as f:
                f.write(base64.b64decode(img_base64))
            img = Image.open(f'./captcha.jpg')
            # if lang == 'cn':
            #     import matplotlib.pyplot as plt
            #     plt.imshow(img)
            #     print('点击所有倒立的汉字，在命令行中按回车提交')
            #     points = plt.ginput(7)
            #     capt = json.dumps({'img_size': [200, 44],
            #                        'input_points': [[i[0] / 2, i[1] / 2] for i in points]})
            # else:
            # img_thread = threading.Thread(target=img.show, daemon=True)
            # img_thread.start()
            # TODO 验证码自动识别实现
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, img.show)
            capt = input('请输入图片里的验证码：')
            # 这里必须先把参数 POST 验证码接口
            await self.post(url, data={'input_text': capt})
            return capt
        return ''

    async def check_login(self) -> bool:
        """
        检查登录状态，访问登录页面出现跳转则是已登录，
        如登录成功保存当前 Cookies
        :return: bool
        """
        url = 'https://www.zhihu.com/'
        async with self.get(url, allow_redirects=False) as r:
            if r.status == 200:
                self.cookie_jar.save(self.cookie_file)
                self.logger.debug(f'保存cookies到->{self.cookie_file}')
                return True
            else:
                self.logger.debug(await r.text())
                self.logger.debug(r.headers)
                self.logger.debug(r.status)
            return False

    async def _get_xsrf(self) -> str:
        """
        从登录页面获取 xsrf
        :return: str
        """
        async with self.get('https://www.zhihu.com/', allow_redirects=False) as r:
            self.logger.debug('尝试获取xsrf token')
            if r.cookies.get('_xsrf'):
                self.logger.debug(f'获取成功{r.cookies.get("_xsrf").value}')
                return r.cookies.get('_xsrf').value
        raise AssertionError('获取 xsrf 失败')

    def _get_signature(self, timestamp: Union[int, str], login_data: dict) -> str:
        """
        通过 Hmac 算法计算返回签名
        实际是几个固定字符串加时间戳
        :param timestamp: 时间戳
        :return: 签名
        """
        ha = hmac.new(b'd1b964811afb40118a12068ff74a12f4', digestmod=hashlib.sha1)
        grant_type = login_data['grant_type']
        client_id = login_data['client_id']
        source = login_data['source']
        ha.update(bytes((grant_type + client_id + source + str(timestamp)), 'utf-8'))
        return ha.hexdigest()

    @staticmethod
    def _encrypt(form_data: dict) -> str:
        with open(f'./encrypt.js') as f:
            js = execjs.compile(f.read())
            return js.call('Q', urlencode(form_data))

    async def get_messages(self, target_hash) -> list:
        headers = self._default_headers
        headers['referer'] = f'https://www.zhihu.com/messages/{target_hash}'
        headers['accept-encoding'] = f'gzip, deflate, br'
        url = f'https://www.zhihu.com/api/v4/chat?sender_id={target_hash}'
        is_end = False
        rst = []
        while not is_end:
            async with self.get(url, headers=headers) as r:
                resp = await r.text()
                resp_json = json.loads(resp)
                if resp_json.get('error'):
                    self.logger.warning(f"登录失败：{resp_json['error']}")
                    return rst
                rst.extend(resp_json['data']['messages'])
                is_end = resp_json['paging']
                if not is_end:
                    url = resp_json['paging']['next']
        return rst

    async def send_message(self, target_hash, content) -> None:
        url = 'https://www.zhihu.com/api/v4/messages'
        data = {"type": "common", "content": content, "receiver_hash": target_hash}
        async with self.post(url, json=data) as r:
            return


if __name__ == '__main__':
    async def test():
        client = ZhihuClient()
        await client.login(load_cookies=True)
        rst = await client.get_messages(config.target_hash)
        print(rst)
        await client.send_message(config.target_hash, '说起来我们学校都禁止电动车入校了，外卖小哥都得骑自行车或者走路（')
        await client.close()

    asyncio.run(test())