import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import json
import time
from datetime import datetime, timezone, timedelta
import sys

sg_timezone = timezone(timedelta(hours=8), name='Asia/Singapore')
singapore_time = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(sg_timezone)
cur_hour = singapore_time.strftime("%H")
cur_min_prefix = singapore_time.strftime("%M")[0]

region_map = {"RHK": "湾仔", "RKO": "九龙", "RKT": "观塘", "FTO": "火炭", "TMO": "屯门", "YLO": "元朗"}
start_day = 20230501
end_day = 20261001
select_days = set([])
free_day = 7
black_time = set([1, 2, 3, 4, 5, 6, 7, 8])


if int(cur_hour) in black_time:
    print("in black_time and exit directly")
    sys.exit(0)


def load_vip_user():
    vip_user = {}
    with open("./conf/vip_user") as data:
        for line in data:
            fields = line.strip().split("\t")
            dt = datetime.strptime(fields[1], "%Y-%m-%d %H:%M:%S")
            tid_set = set()
            if fields[2] != '-':
                for tid in fields[2].split(","):
                    tid_set.add(tid[:3])
            vip_user[fields[0]] = [int(dt.timestamp()), tid_set]

    return vip_user


def parse_res(res):
    region_quota = {}
    for book in res['data']:
        date_time_fields = book['date'].split("/")
        date_time = int(date_time_fields[2] + date_time_fields[0] + date_time_fields[1])
        if date_time < start_day or date_time > end_day:
            continue
        office_id = region_map[book['officeId']]
        if office_id not in region_quota:
            region_quota[office_id] = {'quotaR' : [], 'quotaK': []}
        if book['quotaR'] != 'quota-r' and book['quotaR'] != 'quota-non':
            region_quota[office_id]['quotaR'].append(date_time)
        if book['quotaK'] != 'quota-r' and book['quotaK'] != 'quota-non':
            region_quota[office_id]['quotaK'].append(date_time)
    return region_quota


def get_http_request():
    url = "https://eservices.es2.immd.gov.hk/surgecontrolgate/ticket/getSituation"
    response = requests.get(url)
    region_quota = {}
    if response.status_code == 200:
        res = response.json()
        region_quota = parse_res(res)
    return region_quota


def send_email(result_str):
    sender = 'ynchen721@126.com'
    passwd = "7211248163264"
    receivers = ['yunan.chen@shopee.com']
    message = MIMEMultipart()
    message['From'] = sender
    message['To'] = ",".join(receivers)
    message['Subject'] = 'Quota_Reminder'
    text = MIMEText(result_str, 'plain')
    message.attach(text)
    with smtplib.SMTP('smtp.126.com', 25) as smtp:
        smtp.login(sender, passwd)
        smtp.sendmail(sender, receivers, message.as_string())


def filter_time(region, region_quota, key):
    name_map = {"quotaR": "身份证办理/补办", "quotaK": "身份证旧换新"}
    valid_date = []
    for t in region_quota[region][key]:
        if t >= start_day and t <= end_day:
            if len(select_days) > 0:
                if t in select_days:
                    valid_date.append(str(t))
            else:
                valid_date.append(str(t))
    if len(valid_date) == 0:
        return ''
    return name_map[key] + '\n' + ','.join(valid_date)


def deal_user_info(res, user_info):
    if 'data' in res and 'records' in res['data']:
        for user in res['data']['records']:
            uid = user['uid']
            idkey = user['id']
            createTime = int(user['createTime']) / 1000
            user_info[uid] = [idkey, createTime]


def get_topic_users(vip_user):
    user_info = {}
    url = "https://wxpusher.zjiecode.com/api/fun/wxuser/v2?appToken=AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB&page=1&pageSize=100&type=1&isBlock=True"
    response = requests.get(url)
    if response.status_code == 200:
        deal_user_info(response.json(), user_info)
    url = "https://wxpusher.zjiecode.com/api/fun/wxuser/v2?appToken=AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB&page=1&pageSize=100&type=1&isBlock=False"
    response = requests.get(url)
    if response.status_code == 200:
        deal_user_info(response.json(), user_info)

    cur_ts = int(time.time())
    cur_time = cur_hour + cur_min_prefix

    for userid in user_info:
        is_block = 'true'
        if userid in vip_user and cur_ts < vip_user[userid][0] and (cur_min_prefix == '0' or cur_time in vip_user[userid][1]):
            is_block = 'false'
        elif cur_ts - user_info[userid][1] < free_day * 3600 * 24 and cur_min_prefix == '0':
            is_block = 'false'

        url = "https://wxpusher.zjiecode.com/api/fun/reject?appToken=AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB&id=%s&reject=%s" % (user_info[userid][0], is_block)
        response = requests.put(url)
        print("set %s to be block: %s" % (userid, is_block))


if __name__ == "__main__":
    vip_user = load_vip_user()
    print(cur_hour + cur_min_prefix)
    get_topic_users(vip_user)
    result_str = ''
    region_quota = get_http_request()
    for region in region_quota:
        result_str_1 = filter_time(region, region_quota, 'quotaR')
        result_str_2 = filter_time(region, region_quota, 'quotaK')
        result_str_1 = (result_str_1 + '\n') if result_str_1 != '' else "身份证办理/补办\n当前无可预约时间\n"
        result_str_2 = result_str_2 if result_str_2 != '' else "身份证旧换新\n当前无可预约时间\n"
        result_str += '\n'.join([region, result_str_1, result_str_2]) + '\n========================\n'

    json_temp = {"appToken":"AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB",
            "summary": "身份证预约定时提醒",
            "contentType": 1,
            "verifyPay": False,
            "topicIds":[10054],
            "content": '如需定制化预约名额提醒服务,请联系群主酸奶(微信xhs108082938)\n========================\n' + result_str}

    json_payload = json.dumps(json_temp)
    headers = {"Content-Type": "application/json"}

    if result_str != '':
        try:
            post_url = 'https://wxpusher.zjiecode.com/api/send/message'
            response_wx = requests.post(post_url, data=json_payload, headers=headers)
            print("send_wechat success")
        except:
            print("error occur")
    else:
        print("result_str is empty")
