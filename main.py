from get_grade import *
from push import *
import json
import logging
import sys
import re
from logger import setup_logging
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
# 配置日志
logger = setup_logging()

def load_config():
    try:
        with open(f'{BASE_DIR}/config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error("错误：找不到 config.json 配置文件")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error("错误：config.json 格式不正确")
        sys.exit(1)
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        sys.exit(1)

    base_url = config.get('baseUrl', "https://jwxt.jxufe.edu.cn")
    username = config.get('username')
    password_md5 = config.get('passwordMd5')
    token = config.get('token')
    login_way = config.get('login_way', 0)
    password = config.get('password','')
    fpVisitorId = config.get('fpVisitorId')
    log_level = config.get('log_level', "INFO")
    # 验证 username (纯数字)
    if not username or not str(username).isdigit():
        logger.error("配置校验失败：username 应为纯数字")
        sys.exit(1)

    # 验证 passwordMd5 (32位小写十六进制)
    if not password_md5 or not re.match(r'^[a-f0-9]{32}$', password_md5):
        logger.error("配置校验失败：passwordMd5 应为32位小写十六进制字符串")
        sys.exit(1)

    # 验证 token (非空)
    if not token:
        logger.error("配置校验失败：token 不能为空")
        sys.exit(1)

    return base_url, username, password_md5, token,login_way, password,fpVisitorId, log_level

if __name__ == "__main__":
    logger.info("程序启动")
    base_url, username, onceMd5Password, token, login_way, password, fpVisitorId, log_level = load_config()

    # 设置日志等级
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
     
    try:
        if login_way == 0:
            logger.info("使用 Kingosoft 登录方式")
            #Kingosoft登录方式
            login = XqeLogin(base_url)
            #获取登录必须的参数
            jsessionid, sessionid, deskey, nowtime = login.GetDynamicParams()
            logger.info("动态参数获取成功")
            
            #获取登录参数
            signInParams = login.SignInParamsCombime(username, onceMd5Password, nowtime, deskey, sessionid)
            #登录并获取新的jsessionid
            jsessionid = login.SignIn(signInParams, jsessionid)
            logger.info("登录成功")
        elif login_way == 1:
            logger.info("使用 CAS 登录方式")
            #CAS登录方式
            execution = OALogin.get_execution()
            state = OALogin.get_state(username,password,fpVisitorId)
            TGC = OALogin.get_TGC(username, password, fpVisitorId,execution,state)
            ticket = OALogin.get_ticket(TGC)
            jsessionid = OALogin.get_jsessionid(ticket)
        #获取成绩参数
        schoolYear, term, userCode = XqeGradePull.GetGradeParams(jsessionid, base_url)
        #获取成绩HTML
        Grade_html = XqeGradePull.GetGrade(jsessionid, schoolYear, term, userCode, base_url)
        logger.info(f"获取成绩HTML成功 (学年: {schoolYear}, 学期: {term})")

        #解析成绩HTML为dict格式
        grade = html2dict.parse_grade_html(Grade_html)
        
        #检查是否获取成绩成功
        if grade['error'] != 0:
            error_msg = f"获取成绩失败，错误信息：{grade['error']}"
            logger.error(error_msg)
            Push.send_message("GradeEasyPush 运行错误", error_msg, token)
            sys.exit(1)

        if not Push.check_update(grade):
            logger.info("成绩无更新，程序结束")
            sys.exit(0)
        else:
            logger.info("发现新成绩，准备推送")

        titile, content = Push.edit_message(grade)
        
        if not Push.send_message(titile, content, token):
            logger.error("成绩推送失败")
        else:
            logger.info("成绩推送成功")
            
    except Exception as e:
        logger.exception(f"程序运行过程中发生未知异常: {e}")
        Push.send_message("GradeEasyPush 运行异常", f"程序运行过程中发生未知异常: {e}", token)
        
    logger.info("程序执行完毕")