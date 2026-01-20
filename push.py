import requests
import logging
from get_grade import *
from pathlib import Path

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent

class Push:

    @staticmethod
    def edit_message(message):
        """
        编辑需要发送的成绩信息
        
        :param message: 需要发送的信息
        :return: 标题和内容
        """
        title = f"{message['student_info']['打印时间']}成绩更新通知"
        content = f"""
## 个人信息
姓名：{message['student_info']['姓名']}
学号：{message['student_info']['学号']}
班级：{message['student_info']['行政班级']}
学院：{message['student_info']['院系部']}
## 成绩信息
学期：{message['semester']}
"""
        cource_info = "|课程名称|课程性质|成绩|\n|-|-|-|\n"
        for course in message['courses']:
            cource_info += f"|{course['name'][12:]}|{course['category'].split('/')[-1]}|{course['score']}|\n"
        content += cource_info
        return title, content

    @staticmethod
    def send_message(title,content,token):
        """
        使用showdoc发送成绩信息
        
        :param message: 需要发送的信息
        """
        push_url = f"https://push.showdoc.com.cn/server/api/push/{token}"
        try:
            response  = requests.post(push_url, data={
                "title": title,
                "content": content
            })
            if response.status_code != 200:
                logger.error(f"消息发送HTTP错误: Status Code {response.status_code}")
            elif response.json().get("error_code") != 0:
                logger.error(f"消息发送API错误: {response.json().get('error_message')}")
            else:
                logger.info("消息发送成功")
                return True
        except Exception as e:
            logger.error(f"消息发送异常: {e}")
        return False
    @staticmethod
    def check_update(message):
        """
        检查是否有新的成绩
        
        :param message: 需要检查的信息
        """
        check_message = "" 
        for course in message['courses']:
            check_message += f"{course['name']}:{course['score']}\n"
        new_md5 = XqeLibs.md5(check_message)
        logger.debug(f"当前成绩MD5: {new_md5}")
        
        try:
            with open(f"{BASE_DIR}/data/last_grade.txt", "r") as f:
                last_md5 = f.read().strip()
                logger.debug(f"上次成绩MD5: {last_md5}")
        except FileNotFoundError:
            logger.warning("未找到 last_grade.txt，视为第一次运行")
            last_md5 = None
        except Exception as e:
            logger.error(f"读取 last_grade.txt 失败: {e}")
            last_md5 = None

        if new_md5 != last_md5:
            logger.info("检测到成绩变化，更新本地记录...")
            try:
                with open(f"{BASE_DIR}/data/last_grade.txt", "w") as f:
                    f.write(new_md5)
                return True
            except Exception as e:
                logger.error(f"写入 last_grade.txt 失败: {e}")
                # 即使写入失败，也应该尝试推送，因为确实有更新
                return True
        else:
            logger.debug("成绩无变化")
            return False
