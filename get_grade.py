import requests
import execjs
import base64
import hashlib
import json
from bs4 import BeautifulSoup
import re
import logging
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

_KINGO_DES_JS_CACHE = None
class XqeLibs:
    @staticmethod
    def md5(data):
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def base64_encode(data):
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')
    
    @staticmethod
    def base64_decode(data):
        return base64.b64decode(data.encode('utf-8')).decode('utf-8')
class KingoDES:
    def __init__(self):
        global _KINGO_DES_JS_CACHE
        if _KINGO_DES_JS_CACHE is None:
            with open(f'{BASE_DIR}/jkingo.des.js', 'r', encoding='utf-8') as f:
                _KINGO_DES_JS_CACHE = f.read()
        
        # 每个实例独立编译JS执行环境
        self.kingoDesJs_compiled = execjs.compile(_KINGO_DES_JS_CACHE)
        
    def encrypt_data(self, data, des_key):
        """简化的加密函数"""
        encrypted_hex = self.kingoDesJs_compiled.call("strEnc", data, des_key, None, None)
        encrypted_base64 = base64.b64encode(encrypted_hex.encode('utf-8')).decode('utf-8')
        return encrypted_base64
class XqeLogin:
    def __init__(self, base_url):
        self.base_url = base_url
        # 每个实例独立的会话和加密模块
        self.session = requests.Session()
        self.kingoDes = KingoDES()

    def GetDynamicParams(self):
        """初始化加密模块与会话"""
        """获取Session$JSESSIONID"""
        logger.info("开始获取登录动态参数...")
        url = f"{self.base_url}/cas/login.action"
        try:
            response = self.session.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"获取JSESSIONID失败: {e}")
            raise Exception(f"网络请求错误：{e}")

        # 从Cookie获取JSESSIONID
        jsessionid = self.session.cookies.get('JSESSIONID')
        if not jsessionid:
            logger.error("Cookie中未找到JSESSIONID")
            raise ValueError("无法获取JSESSIONID")
        
        # 获取Session ID
        content = response.text
        match = re.search(r'var\s+_sessionid\s*=\s*"([A-F0-9]+)"', content)
        sessionid = match.group(1) if match else None
        
        """获取deskey&nowtime"""
        # Get encryption parameters
        getTempDeskey_url = f"{self.base_url}/frame/homepage?method=getTempDeskey"
        getTempNowtime_url = f"{self.base_url}/frame/homepage?method=getTempNowtime"
        try:
            deskey_response = self.session.get(getTempDeskey_url)
            deskey_response.raise_for_status()
            nowtime_response = self.session.get(getTempNowtime_url)
            nowtime_response.raise_for_status()
        except Exception as e:
            logger.error(f"获取加密参数(deskey/nowtime)失败: {e}")
            raise Exception(f"获取加密参数失败：{e}")
        
        deskey = deskey_response.text
        nowtime = nowtime_response.text

        # 错误检测
        if not jsessionid or not sessionid or not deskey or not nowtime:
            logger.error(f"动态参数获取不完整: jsessionid={bool(jsessionid)}, sessionid={bool(sessionid)}, deskey={bool(deskey)}, nowtime={bool(nowtime)}")
            raise ValueError("获取动态参数失败")

        logger.debug("动态参数获取成功")
        return jsessionid, sessionid, deskey, nowtime

    def SignInParamsCombime(self, originUsername, onceMd5Password, timestamp, deskey, session_id):
        """注意：传入的timestamp应当是服务器时间（格式为：2025-10-26 00:17:41）"""        
        ## 第一步最初的数据整合：_u=<base64:"学号;;sessionid">==&_p=<md5(密码)md5("")>&randnumber=&isPasswordPolicy=1&txt_mm_expression=14&txt_mm_length=15&txt_mm_userzh=0&hid_flag=1&hidlag=1&hid_dxyzm=
        params_u = XqeLibs.base64_encode(originUsername + ';;' + session_id)
        params_p = XqeLibs.md5(onceMd5Password + XqeLibs.md5("")) 

        paramsV1 = "_u=" + params_u + "&_p=" + params_p + "&randnumber=&isPasswordPolicy=1&txt_mm_expression=14&txt_mm_length=15&txt_mm_userzh=0&hid_flag=1&hidlag=1&hid_dxyzm="

        ## 生成token
        token = XqeLibs.md5(XqeLibs.md5(paramsV1) + XqeLibs.md5(timestamp))

        ## 第二步模拟动态加载的js模块的getEncParams()函数
        paramsV1_desEncoded = self.kingoDes.encrypt_data(paramsV1, deskey)

        paramsV2 = "params=" + paramsV1_desEncoded + "&token="+token+"&timestamp="+timestamp

        ## 第三部最后合并
        paramsV3 = paramsV2 + "&deskey=" + deskey + "&ssessionid=" + session_id
        
        return paramsV3

    def SignIn(self, params, jsessionid):
        logger.info("开始执行登录...")
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': f"{self.base_url}/cas/login.action",
            'Cookie': f"JSESSIONID={jsessionid}"
        }
        
        login_url = f"{self.base_url}/cas/logon.action"

        # 发送登录请求
        try:
            response = self.session.post(login_url, data=params, headers=headers)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"登录请求网络错误: {e}")
            raise Exception(f"网络请求错误： {e}")

        # 判断登录结果
        try:
            response_json = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("登录响应不是有效的JSON格式")
            raise Exception("登录响应格式错误")
            
        if response_json.get("status") != "200":
            logger.warning(f"登录失败: {response_json.get('message', '未知错误')}")
            raise Exception(f"登录失败: {response_json.get('message', '未知错误')}")
        
        ## 获取新的JSESSIONID
        updatedJsessionId = response.cookies.get('JSESSIONID')
        if not updatedJsessionId:
            logger.error("登录成功但未获取到新的JSESSIONID")
            raise Exception("登录后未能获取新的JSESSIONID")
        
        logger.info("登录成功")
        return updatedJsessionId
    
class XqeGradePull:
    @staticmethod
    def GetGradeParams(jsessionid, base_url):
        logger.info("获取学年学期等参数...")
        # 请求成绩
        headers = {
            "Referer": f"{base_url}/jw/common/showYearTerm.action",
            "Cookie": f"JSESSIONID={jsessionid}",
        }
        try:
            response = requests.get(f"{base_url}/jw/common/showYearTerm.action", headers=headers)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"获取个人信息请求失败: {e}")
            raise Exception(f"获取个人信息时出错: {e}")
        
        # 匹配结果
        try:
            response_json = json.loads(response.text)
            schoolYear = response_json['xn']
            term = response_json['xqM']
            userCode = response_json['userCode']
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"解析个人信息JSON失败: {e}")
            raise Exception(f"解析用户信息失败: {e}")

        if not schoolYear or not term:
            logger.error("个人信息中缺失学年或学期")
            raise Exception("无法获取用户信息")
        
        logger.debug(f"获取到参数: schoolYear={schoolYear}, term={term}, userCode={userCode}")
        return schoolYear, term, userCode
        
    @staticmethod    
    def GetGrade(jsessionid, schoolYear, term, userCode, base_url):
        logger.info("开始请求成绩HTML...")
        headers = {"Cache-Control": "max-age=0", "Sec-Ch-Ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"", "Sec-Ch-Ua-Mobile": "?0", "Sec-Ch-Ua-Platform": "\"Windows\"", "Origin": "https://jwxt.jxufe.edu.cn", "Content-Type": "application/x-www-form-urlencoded", "Upgrade-Insecure-Requests": "1", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7", "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document", "Referer": f"{base_url}/student/xscj.stuckcj_data10421.jsp", "Accept-Encoding": "gzip, deflate, br", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", "Priority": "u=0, i", "Connection": "keep-alive"}

        cookies = {"JSESSIONID": f"{jsessionid}"}
        data = {"sjxz": "sjxz3", "ysyx": "yxcj", "zx": "1", "fx": "1", "xn": f"{schoolYear}", "xn1": f"{int(schoolYear)+1}", "xq": "0\r\n"}

        # 请求成绩
        try:
            response = requests.post(f"{base_url}/student/xscj.stuckcj_data10421.jsp",cookies=cookies, headers=headers,data=data)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"请求成绩页面失败: {e}")
            raise Exception(f"从教务系统获取成绩时出现错误：{e}")

        logger.info(f"成绩页面下载成功，长度: {len(response.text)}")
        return response.text
    
class html2dict:
    @staticmethod
    def parse_grade_html(grade_html):
        """
        解析成绩HTML为dict格式
        """
        logger.info("开始解析成绩HTML...")
        if not grade_html:
            logger.error("HTML内容为空")
            return {"error": "HTML content is empty"}
        try:
            soup = BeautifulSoup(grade_html, 'html.parser')
            result = {
                "error": None,
                "student_info": {},
                "semester": "",
                "courses": [],
                "summary": []
            }
            # 1. 解析学生基本信息 (div group="group")
            group_div = soup.find('div', attrs={'group': 'group'})
            if group_div:
                for item in group_div.find_all('div'):
                    text = item.get_text(strip=True)
                    if '：' in text:
                        parts = text.split('：', 1)
                        key = parts[0].replace("(", "").replace(")", "").replace("/", "") # 清洗key
                        value = parts[1]
                        result["student_info"][key] = value
            # 2. 解析学年学期
            # 查找包含"学年学期："的文本
            semester_tag = soup.find(lambda tag: tag.name == "td" and "学年学期：" in tag.get_text())
            if semester_tag:
                result["semester"] = semester_tag.get_text(strip=True).replace("学年学期：", "")
            # 3. 解析表格数据
            tables = soup.find_all('table')
            
            # 寻找成绩表
            grade_table = None
            summary_table = None
            for table in tables:
                text = table.get_text()
                if "课程/环节" in text:
                    grade_table = table
                elif "修读课程环节数" in text or "获得平均学分绩点" in text:
                    summary_table = table
            # 处理成绩明细表
            if grade_table:
                tbody = grade_table.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        tds = tr.find_all('td')
                        if len(tds) >= 10: # 确保行结构正确
                            course = {
                                "seq": tds[0].get_text(strip=True),         # 序号
                                "name": tds[1].get_text(strip=True),        # 课程/环节
                                "credit": tds[2].get_text(strip=True),      # 学分
                                "category": tds[3].get_text(strip=True),    # 类别
                                "property": tds[4].get_text(strip=True),    # 修读性质
                                "exam_type": tds[5].get_text(strip=True),   # 考核方式
                                "score": tds[6].get_text(strip=True),       # 成绩
                                "earned_credit": tds[7].get_text(strip=True), # 获得学分
                                "gpa": tds[8].get_text(strip=True),         # 绩点
                                "gpa_points": tds[9].get_text(strip=True),  # 学分绩点
                                "remark": tds[10].get_text(strip=True)      # 备注
                            }
                            result["courses"].append(course)
            # --- 处理汇总表 ---
            if summary_table:
                tbody = summary_table.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        tds = tr.find_all('td')
                        if len(tds) >= 7:
                            summary_item = {
                                "type": tds[0].get_text(strip=True),          # 类型 (必修课/合计等)
                                "count": tds[1].get_text(strip=True),         # 门数
                                "credits": tds[2].get_text(strip=True),       # 学分
                                "earned_credits": tds[3].get_text(strip=True),# 获得学分
                                "earned_gpa": tds[4].get_text(strip=True),    # 获得绩点
                                "gpa_points": tds[5].get_text(strip=True),    # 获得学分绩点
                                "avg_gpa": tds[6].get_text(strip=True)        # 平均学分绩点
                            }
                            result["summary"].append(summary_item)
            
            logger.info(f"解析成功，找到 {len(result['courses'])} 门课程")
            result["error"] = 0
            return result
        except Exception as e:
            logger.exception(f"解析HTML时出错: {e}")
            result["error"] = f"解析HTML时出错: {e}"
            return result
        return result
