import requests
import json
import yagmail
import re
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from base64 import b64encode
import urllib.parse


def MsgSend(message_title, message_info):
    if os.environ['mail_address']:
        mail = yagmail.SMTP(os.environ['mail_address'],
                            os.environ['mail_password'], os.environ['mail_host'])
        try:
            mail.send(os.environ['receive_mail'], message_title, message_info)
        except Exception as e:
            print("推送出错！", str(e))
    if os.environ['sct_ftqq']:
        try:
            requests.get(f'https://sctapi.ftqq.com/{os.environ["sct_ftqq"]}.send?{urllib.parse.urlencode({"title":message_title, "desp":message_info})}')
        except Exception as e:
            print("推送出错！", str(e))

def encrypt(t, e):
    t = str(t)
    key = e.encode('utf-8')
    cipher = AES.new(key, AES.MODE_ECB)
    padded_text = pad(t.encode('utf-8'), AES.block_size)
    encrypted_text = cipher.encrypt(padded_text)
    return b64encode(encrypted_text).decode('utf-8')


# 获取学校ID
def get_school_id(school_name):
    headers00 = {
    "accept": "application/json, text/plain, */*",
    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 Edg/119.0.0.0"}
    url00 = "https://gw.wozaixiaoyuan.com/basicinfo/mobile/login/getSchoolList"
    response00 = requests.get(url00, headers=headers00)
    data = json.loads(response00.text)['data']
    for school in data:
        if school['name'] == school_name:
            return school['id']
    return None

def Login(headers, username, password):
    key = (str(username) + "0000000000000000")[:16]
    encrypted_text = encrypt(password, key)
    login_url = 'https://gw.wozaixiaoyuan.com/basicinfo/mobile/login/username'
    params = {
        "schoolId": school_id,
        "username": username,
        "password": encrypted_text
    }
    login_req = requests.post(login_url, params=params, headers=headers)
    text = json.loads(login_req.text)
    if text['code'] == 0:
        print(f"{username}账号登陆成功！")
        set_cookie = login_req.headers['Set-Cookie']
        jws = re.search(r'JWSESSION=(.*?);', str(set_cookie)).group(1)
        return jws
    else:
        print(f"{username}登陆失败，请检查账号密码！")
        return False


# 获取我的日志
def GetMySignLogs(headers, school_area, username):
    url = 'https://gw.wozaixiaoyuan.com/sign/mobile/receive/getMySignLogs'
    params = {
        'page': 1,
        'size': 10
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"获取打卡日志API请求失败，状态码: {response.status_code}, 响应: {response.text}")
        return False, False, False
    
    response_data = response.json()
    if response_data.get('code') != 0 or not response_data.get('data'):
        print(f"获取打卡日志API返回错误或无数据: {response_data}")
        return False, False, False

    if not response_data['data']:
        print("获取打卡日志API返回数据为空列表，可能当前无打卡任务。")
        return False, False, False

    data = response_data['data'][0]
    print(f"[调试日志] GetMySignLogs - 原始data对象: {data}")
    print(f"[调试日志] GetMySignLogs - data对象的键: {list(data.keys())}")

    sign_status = data.get('signStatus', -1)
    sign_title = data.get('signTitle', '')

    # 检查任务状态，只有待签到状态才需要打卡
    if int(sign_status) != 1:
        print(f"用户已打过卡或任务非待签到状态 (signStatus: {sign_status})！")
        return False, False, False

    # 显示当前任务信息（包括请假相关任务）
    print(f"检测到待签到任务: '{sign_title}'，准备执行打卡")
    
    # 获取基本信息
    signId = data.get('signId')
    log_id = data.get('id')
    
    if not all([signId, log_id]):
        print(f"获取打卡日志关键信息不完整。signId: {signId}, id: {log_id}")
        return False, False, False

    # 检查是否有areaList字段
    areaData = data.get('areaList')
    if areaData:
        # 如果有areaList，使用原来的逻辑
        userArea = data.get('userArea', school_area)
        for area in areaData:
            if userArea == area.get('name'):
                dataStr = area.get('dataStr', '')
                if not dataStr and area.get('longitude') and area.get('latitude'):
                    dataStr = f'[{{"longitude": {area.get("longitude")}, "latitude": {area.get("latitude")}}}]'
                
                dataJson = {
                    "type": 1,
                    "polygon": dataStr,
                    "id": area.get('id'),
                    "name": area.get('name'),
                }
                return signId, log_id, dataJson
        print(f"[调试日志] 未能在areaData中找到匹配的区域: {userArea}")
        return False, False, False
    else:
        # 如果没有areaList，尝试从data中直接获取区域信息
        print(f"[调试日志] 未找到areaList字段，尝试从data中获取区域信息")
        
        # 尝试获取经纬度信息
        longitude = data.get('longitude') or data.get('lng')
        latitude = data.get('latitude') or data.get('lat')
        
        if longitude and latitude:
            dataStr = f'[{{"longitude": {longitude}, "latitude": {latitude}}}]'
            dataJson = {
                "type": 1,
                "polygon": dataStr,
                "id": data.get('areaId', log_id),
                "name": school_area,
            }
            return signId, log_id, dataJson
        else:
            # 如果都没有，创建一个默认的区域配置
            print(f"[调试日志] 未找到经纬度信息，使用默认配置")
            dataJson = {
                "type": 1,
                "polygon": "",
                "id": log_id,
                "name": school_area,
            }
            return signId, log_id, dataJson


def GetPunchData(username, location, tencentKey, dataJson):
    geocode = requests.get("https://apis.map.qq.com/ws/geocoder/v1", params={"address": location, "key": tencentKey})
    geocode_data = json.loads(geocode.text)
    if geocode_data['status'] == 0:
        reverseGeocode = requests.get("https://apis.map.qq.com/ws/geocoder/v1", params={"location": f"{geocode_data['result']['location']['lat']},{geocode_data['result']['location']['lng']}", "key": tencentKey})
        reverseGeocode_data = json.loads(reverseGeocode.text)
        if reverseGeocode_data['status'] == 0:
            location_data = reverseGeocode_data['result']
            
            # 处理 polygon 数据
            if dataJson.get('polygon') and dataJson['polygon'].strip():
                try:
                    dataJson['polygon'] = json.loads(dataJson['polygon'])
                except json.JSONDecodeError:
                    print(f"[调试日志] polygon数据解析失败，使用默认值")
                    dataJson['polygon'] = []
            else:
                dataJson['polygon'] = []
            
            PunchData = {
                "latitude": location_data['location']['lat'],
                "longitude": location_data['location']['lng'],
                "nationcode": "",
                "country": "中国",
                "province": location_data['ad_info']['province'],
                "citycode": "",
                "city": location_data['ad_info']['city'],
                "adcode": location_data['ad_info']['adcode'],
                "district": location_data['ad_info']['district'],
                "towncode": location_data['address_reference']['town']['id'],
                "township": location_data['address_reference']['town']['title'],
                "streetcode": "",
                "street": location_data['address_component']['street']
            }
            
            # 只有在有有效polygon数据时才添加区域相关字段
            if dataJson.get('polygon'):
                PunchData["inArea"] = 1
                PunchData["areaJSON"] = json.dumps(dataJson, ensure_ascii=False)
            
            return PunchData
    
    print(f"腾讯地图API调用失败，geocode状态: {geocode_data.get('status', 'unknown')}")
    return None


def Punch(headers, punchData, username, log_id, signId):
    if not punchData:
        print(f"{username}打卡数据获取失败，无法进行打卡")
        MsgSend("打卡失败！", f"{username}打卡数据获取失败")
        return False
        
    headers['Referer'] = 'https://servicewechat.com/wxce6d08f781975d91/200/page-frame.html'
    url = 'https://gw.wozaixiaoyuan.com/sign/mobile/receive/doSignByArea'
    params = {
        'id': log_id,
        'schoolId': school_id,
        'signId': signId
    }
    
    print(f"[调试日志] 打卡请求参数: {params}")
    print(f"[调试日志] 打卡数据: {json.dumps(punchData, ensure_ascii=False)}")
    
    try:
        res = requests.post(url, data=json.dumps(punchData), headers=headers, params=params)
        txt = json.loads(res.text)
        
        print(f"[调试日志] 打卡响应: {txt}")
        
        if txt['code'] == 0:
            print(f"{username}打卡成功！\n")
            MsgSend("打卡成功！", f"{username}归寝打卡成功！")
            return True
        else:
            print(f"{username}打卡失败！错误信息: {txt.get('message', '未知错误')}")
            MsgSend("打卡失败！", f"{username}归寝打卡失败！错误: {txt.get('message', str(txt))}")
            return False
    except Exception as e:
        print(f"{username}打卡请求异常: {str(e)}")
        MsgSend("打卡失败！", f"{username}打卡请求异常: {str(e)}")
        return False


# 蓝牙签到模块开始 By Mudea661
def upload_blue_data(blue1, blue2, headers, id, signid):
    username = os.environ['wzxy_username']
    data = {
        "blue1": blue1,
        "blue2": list(blue2.values())
    }
    response = requests.post(
        url=f"https://gw.wozaixiaoyuan.com/dormSign/mobile/receive/doSignByDevice?id={id}&signId={signid}",
        headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get("code") == 0:
            MsgSend(f"账号- {username} -蓝牙打卡成功！", f"账号- {username} -蓝牙打卡成功！")
            return 0
        else:
            MsgSend(f"账号- {username} -蓝牙打卡失败！", f"账号- {username} -蓝牙打卡失败！")
            return 1
    else:
        return 1


def doBluePunch(headers, username):
    # 获取签到日志
    sign_logs_url = "https://gw.wozaixiaoyuan.com/dormSign/mobile/receive/getMySignLogs"
    sign_logs_params = {
        "page": 1,
        "size": 10
    }
    try:
        response = requests.get(sign_logs_url, headers=headers, params=sign_logs_params)
        data_ids = response.json()
        location_id = data_ids["data"][0]["locationId"]
        sign_id = data_ids["data"][0]["signId"]
        major = data_ids["data"][0]["deviceList"][0]["major"]
        uuid = data_ids["data"][0]["deviceList"][0]["uuid"]
        blue1 = [uuid.replace("-", "") + str(major)]
        blue2 = {"UUID1": uuid}
    except:
        MsgSend(f"账号- {username} -获取签到列表出错！", f"账号- {username} -获取签到列表出错！")
        return 0
    return upload_blue_data(blue1, blue2, headers, location_id, sign_id)

# 蓝牙模块结束


def main():
    global school_id
    username = os.environ['wzxy_username']
    school_area = os.environ.get('WZXY_SCHOOL_AREA')
    if not school_area:
        print("错误：环境变量 WZXY_SCHOOL_AREA 未设置！请在 GitHub Secrets 中配置。")
        MsgSend("打卡配置错误", f"{username} 的 WZXY_SCHOOL_AREA 环境变量未设置！")
        return False

    school_id = get_school_id(os.environ['school_name'])
    login_headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; WLZ-AN00 Build/HUAWEIWLZ-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.99 XWEB/4343 MMWEBSDK/20220903 Mobile Safari/537.36 MMWEBID/4162 MicroMessenger/8.0.28.2240(0x28001C35) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 miniProgram/wxce6d08f781975d91'}
    jws = Login(login_headers, username,
                             os.environ['wzxy_password'])
    if jws:
        headers = {
            'Host': 'gw.wozaixiaoyuan.com',
            'Connection': 'keep-alive',
            'Accept': 'application/json, text/plain, */*',
            'jwsession': jws,
            "cookie": f'JWSESSION={jws}',
            "cookie": f'JWSESSION={jws}',
            "cookie": f'WZXYSESSION={jws}',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; WLZ-AN00 Build/HUAWEIWLZ-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.99 XWEB/4343 MMWEBSDK/20220903 Mobile Safari/537.36 MMWEBID/4162 MicroMessenger/8.0.28.2240(0x28001C35) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 miniProgram/wxce6d08f781975d91',
            'Content-Type': 'application/json;charset=UTF-8',
            'X-Requested-With': 'com.tencent.mm',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://gw.wozaixiaoyuan.com/h5/mobile/health/0.3.7/health',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        if os.environ['dorm_sign'] == 'yes':
            signId, log_id, dataJson = GetMySignLogs(headers, school_area, username) # id 改为 log_id
            if not signId:
                return False
            punchData = GetPunchData(username, os.environ['punch_location'], os.environ['tencentKey'], dataJson)
            Punch(headers, punchData, username, log_id, signId) # id 改为 log_id
            return True
        if os.environ['blue_sign'] == 'yes':
            doBluePunch(headers, username)

    else:
        MsgSend(f"{username} 登陆失败！", f"{username} 登陆失败！")
        return False


if __name__ == "__main__":
    main()
