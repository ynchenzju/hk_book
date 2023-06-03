import requests
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import json
import time
import traceback
from datetime import datetime

region_map = {"RHK": "湾仔", "RKO": "长沙湾", "RKT": "观塘", "FTO": "火炭", "TMO": "屯门", "YLO": "元朗"}
global_start_day = '2023-05-01'
global_end_day = '2025-10-01'
uid_ts = {}

f1 = open("./log/send_info.log", "w")
f2 = open("./log/error_info.log", "w")
f3 = open("./log/run_info.log", "w")

def load_conf(book_conf):
    with open("./conf/book.conf") as data:
        for line in data:
            _, uid, start_day, end_day, select_days, weekdays, locations, book_type, flag = line.strip().split("\t")
            if flag == '0':
                continue
            book_conf[uid] = {}
            book_conf[uid]['st'] = start_day
            book_conf[uid]['ed'] = end_day
            book_conf[uid]['select_days'] = set(select_days.split(",")) if select_days != "-" else ''
            book_conf[uid]['weekdays'] = set(weekdays.split(",")) if weekdays != '-' else ''
            book_conf[uid]['locations'] = set(locations.split(",")) if locations != '-' else ''
            book_conf[uid]['book_type'] = book_type


def parse_res(res):
    region_quota = {}
    for book in res['data']:
        date_time_fields = book['date'].split("/")
        date_time = date_time_fields[2] + '-' + date_time_fields[0] + '-' + date_time_fields[1]
        if date_time < global_start_day or date_time > global_end_day:
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

def get_week_day(t):
    date_format = "%Y-%m-%d"
    date_object = datetime.strptime(t, date_format)
    weekday = date_object.weekday()
    weekday_str = date_object.strftime("%A")[:3]

    return str(weekday + 1), weekday_str


def get_valid_result(region, region_quota, user_conf, key, book_type):
    name_map = {"0": "申领身份证时段", "1": "身份证旧换新时段"}
    valid_date = []
    for t in region_quota[region][key]:
        if t < user_conf['st'] or t > user_conf['ed']:
            continue
        if user_conf['select_days'] != '' and t not in user_conf['select_days']:
            continue
        weekday, weekday_str = get_week_day(t)
        if user_conf['weekdays'] != '' and weekday not in user_conf['weekdays']:
            continue
        valid_date.append(t + ' ' + weekday_str)

    if len(valid_date) > 0:
        title = name_map[book_type]
        return title + '\n' + ', '.join(valid_date)
    return ''


def filter_time(region, region_quota, user_conf):
    result_str_1 = ''
    result_str_2 = ''
    if user_conf['book_type'] == '0':
        result_str_1 = get_valid_result(region, region_quota, user_conf, 'quotaR', '0')
    elif user_conf['book_type'] == '1':
        result_str_2 = get_valid_result(region, region_quota, user_conf, 'quotaK', '1')
    elif user_conf['book_type'] == '2':
        result_str_1 = get_valid_result(region, region_quota, user_conf, 'quotaR', '0')
        result_str_2 = get_valid_result(region, region_quota, user_conf, 'quotaK', '1')

    return result_str_1, result_str_2


def get_book_response(book_conf, region_quota):
    uid_2_res = {}
    for uid in book_conf:
        user_conf = book_conf[uid]
        result_str_list = []
        for region in region_quota:
            locations = user_conf['locations']
            if locations == '' or region in locations:
                result_str_1, result_str_2 = filter_time(region, region_quota, user_conf)
                if result_str_1 != '' or result_str_2 != '':
                    result_str_list.append(region + '\n' + result_str_1 + '\n' + result_str_2)

        uid_2_res[uid] = ''
        if len(result_str_list) > 0:
            uid_2_res[uid] = result_str_list
    return uid_2_res

def post_message(book_conf, uid_2_res):
    json_temp = {"appToken":"AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB",
        "summary": "香港身份证预约情况",
        "contentType": 1,
        "verifyPay": False,
    }
    headers = {"Content-Type": "application/json"}

    for uid in uid_2_res:
        if len(uid_2_res[uid]) == 0:
            print("%s wechat message is empty" % uid)
            continue
        json_temp['uids'] = [uid]
        json_temp['content'] = '请尽快预约防止被黄牛抢占\n=========\n' + "\n=========\n".join(uid_2_res[uid]) + '\n'
        json_payload = json.dumps(json_temp)
        try:
            ts = int(time.time())
            if uid not in uid_ts or uid_ts[uid] < ts:
                post_url = 'https://wxpusher.zjiecode.com/api/send/message'
                response_wx = requests.post(post_url, data=json_payload, headers=headers)
                sys.stdout = f1
                print("%u: send %s wechat success" % (ts, uid))
                uid_ts[uid] = ts + 700
                sys.stdout.flush()
                send_email(json_temp['content'])
            else:
                sys.stdout = f1
                print("%u: %s is replicate output" % (ts, uid))
                sys.stdout.flush()
        except:
            sys.stdout = f2
            print("error occur")
            traceback.print_exc(file=f2)
            sys.stdout.flush()
            sys.exit(1)

if __name__ == "__main__":
    cnt = 0
    while True:
        book_conf = {}
        load_conf(book_conf)
        region_quota = get_http_request()
        uid_2_res = get_book_response(book_conf, region_quota)
        post_message(book_conf, uid_2_res)
        cnt += 1
        sys.stdout = f3
        print("run %d times" % cnt)
        sys.stdout.flush()
        time.sleep(15)

    f1.close()
    f2.close()
