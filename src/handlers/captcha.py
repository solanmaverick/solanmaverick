import aiohttp
import base64
import asyncio
import time
import json
import random
from typing import Optional, Dict
from ..utils.logger import logger
from ..utils.config import config

# ... 其余代码保持不变 ...

class CaptchaSolver:
    def __init__(self):
        self.api_key = "a37a239633d486857a9eea4bf3d2d7d5"  # 2captcha API key
        self.api_url = "http://2captcha.com/in.php"
        self.result_url = "http://2captcha.com/res.php"
        self.session: Optional[aiohttp.ClientSession] = None
        self.max_attempts = config.get('captcha.max_attempts', 30)
        self.check_interval = config.get('captcha.check_interval', 5)
        self.timeout = config.get('captcha.timeout', 180)

    async def initialize(self):
        """初始化会话"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self.api_key
                }
            )

    async def solve(self, image_url: str) -> Optional[str]:
        """解决验证码"""
        try:
            if not self.session:
                await self.initialize()

            # 下载验证码图片
            image_data = await self._download_image(image_url)
            if not image_data:
                return None

            # 创建任务
            task_id = await self._create_task(image_data)
            if not task_id:
                return None

            # 获取结果
            return await self._get_solution(task_id)

        except Exception as e:
            logger.error(f"Captcha solving error: {str(e)}")
            return None
        
    async def _download_image(self, url: str) -> Optional[bytes]:
        """下载验证码图片"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                logger.error(f"Failed to download image: {response.status}")
                return None
        except Exception as e:
            logger.error(f"Image download error: {str(e)}")
            return None

    async def _create_task(self, image_data: bytes) -> Optional[str]:
        """创建验证码识别任务"""
        try:
            # 将图片转换为base64
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # 构建请求数据
            task_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": "ImageToTextTask",
                    "body": base64_image
                }
            }

            async with self.session.post(self.api_url, json=task_data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('errorId') == 0:
                        return result.get('taskId')
                    else:
                        logger.error(f"Create task error: {result.get('errorDescription')}")
                else:
                    logger.error(f"Create task failed: {response.status}")
                return None

        except Exception as e:
            logger.error(f"Create task error: {str(e)}")
            return None

    async def _get_solution(self, task_id: str) -> Optional[str]:
        """获取验证码解决方案"""
        max_attempts = config.get('captcha.max_attempts', 30)
        check_interval = config.get('captcha.check_interval', 2)

        try:
            for _ in range(max_attempts):
                solution = await self._check_solution(task_id)
                if solution:
                    return solution
                await asyncio.sleep(check_interval)

            logger.error("Max attempts reached waiting for solution")
            return None

        except Exception as e:
            logger.error(f"Get solution error: {str(e)}")
            return None

    async def _check_solution(self, task_id: str) -> Optional[str]:
        """检查任务结果"""
        try:
            data = {
                "clientKey": self.api_key,
                "taskId": task_id
            }

            async with self.session.post(self.get_result_url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get('errorId') == 0:
                        status = result.get('status')
                        
                        if status == 'ready':
                            return result.get('solution', {}).get('text')
                        elif status == 'processing':
                            return None
                        else:
                            logger.error(f"Unexpected task status: {status}")
                            return None
                    else:
                        logger.error(f"Check solution error: {result.get('errorDescription')}")
                        return None
                else:
                    logger.error(f"Check solution failed: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Check solution error: {str(e)}")
            return None

    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
            self.session = None

    async def solve_hcaptcha(self, sitekey: str, url: str) -> str:
        """解决hCaptcha验证"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()

            # 提交验证码任务
            params = {
                'key': self.api_key,
                'method': 'hcaptcha',
                'sitekey': sitekey,
                'pageurl': url,
                'json': 1,
                'invisible': 1,  # Discord使用隐藏式hCaptcha
                'data': json.dumps({
                    "rqdata": None,
                    "sentry": False,
                    "motionData": {
                        "st": time.time() * 1000,
                        "dct": time.time() * 1000
                    }
                })
            }

            # 提交任务
            async with self.session.get(
                'http://2captcha.com/in.php',
                params=params
            ) as resp:
                text = await resp.text()
                if text.startswith('OK|'):
                    task_id = text.split('|')[1]
                    print(f"hCaptcha task created: {task_id}")
                else:
                    raise Exception(f"Failed to create task: {text}")

            # 等待结果
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                await asyncio.sleep(self.check_interval)
                
                async with self.session.get(
                    'http://2captcha.com/res.php',
                    params={
                        'key': self.api_key,
                        'action': 'get',
                        'id': task_id
                    }
                ) as resp:
                    text = await resp.text()
                    if text.startswith('OK|'):
                        return text.split('|')[1]
                    elif text != 'CAPCHA_NOT_READY':
                        raise Exception(f"Failed to solve captcha: {text}")

            raise Exception("Captcha solving timeout")

        except Exception as e:
            print(f"hCaptcha solving error: {str(e)}")
            raise