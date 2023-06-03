import requests
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import json
import time
import traceback
import random
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

region_map = {"RHK": "湾仔", "RKO": "长沙湾", "RKT": "观塘", "FTO": "火炭", "TMO": "屯门", "YLO": "元朗"}
global_start_day = '2023-05-01'
global_end_day = '2025-10-01'
sendid_ts = {}
uid_ts = {}

log_record_list = []

def init_logger():
    logger = logging.getLogger('my_logger')
    logger.setLevel(logging.DEBUG)
    handler = TimedRotatingFileHandler('./log/hk_book_v2.log', when='H', interval=3, backupCount=8)
    handler.setLevel(logging.DEBUG)
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = init_logger()
current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_conf(book_conf):
    load_cnt = 0
    cur_ts = int(time.time())
    with open("./conf/book.conf") as data:
        for line in data:
            index, id_name, uid, sendid, start_day, end_day, select_days, weekdays, locations, book_type, flag = line.strip().split("\t")
            if flag == '0' or flag == 'flag':
                continue

            ori_uid = uid
            if uid == '-':
                uid = index

            if uid in uid_ts and cur_ts < uid_ts[uid]:
                continue

            book_conf[uid] = {}
            book_conf[uid]['ori_uid'] = ori_uid
            book_conf[uid]['st'] = start_day
            book_conf[uid]['ed'] = end_day
            book_conf[uid]['sendid'] = sendid
            book_conf[uid]['select_days'] = set(select_days.split(",")) if select_days != "-" else ''
            book_conf[uid]['weekdays'] = set(weekdays.split(",")) if weekdays != '-' else ''
            book_conf[uid]['locations'] = set(locations.split(",")) if locations != '-' else ''
            book_conf[uid]['book_type'] = int(book_type)
            book_conf[uid]['log_key'] = id_name
            if ori_uid != '-':
                book_conf[uid]['log_key'] = ori_uid
            load_cnt += 1
    return load_cnt


def parse_res(res):
    region_quota = {}
    for res_book in res['data']:
        date_time_fields = res_book['date'].split("/")
        date_time = date_time_fields[2] + '-' + date_time_fields[0] + '-' + date_time_fields[1]
        if date_time < global_start_day or date_time > global_end_day:
            continue
        office_id = region_map[res_book['officeId']]
        if office_id not in region_quota:
            region_quota[office_id] = {'quotaR' : [], 'quotaK': []}
        if res_book['quotaR'] != 'quota-r' and res_book['quotaR'] != 'quota-non':
            region_quota[office_id]['quotaR'].append(date_time)
        if res_book['quotaK'] != 'quota-r' and res_book['quotaK'] != 'quota-non':
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
    region_result = []
    for t in region_quota[region][key]:
        if t < user_conf['st'] or t > user_conf['ed']:
            continue
        if user_conf['select_days'] != '' and t not in user_conf['select_days']:
            continue
        weekday, weekday_str = get_week_day(t)
        if user_conf['weekdays'] != '' and weekday not in user_conf['weekdays']:
            continue
        region_result.append(t + ' ' + weekday_str)

    return region_result


def filter_time(region, region_quota, user_conf):
    quotaR = []
    quotaK = []
    if user_conf['book_type'] == 0:
        quotaR = get_valid_result(region, region_quota, user_conf, 'quotaR', '0')
    elif user_conf['book_type'] == 1:
        quotaK = get_valid_result(region, region_quota, user_conf, 'quotaK', '1')
    elif user_conf['book_type'] == 2:
        quotaR = get_valid_result(region, region_quota, user_conf, 'quotaR', '0')
        quotaK = get_valid_result(region, region_quota, user_conf, 'quotaK', '1')

    return quotaR, quotaK


def get_book_response(book_conf, region_quota):
    sendid_2_res = {}
    for uid in book_conf:
        user_conf = book_conf[uid]
        sendid = user_conf['sendid']
        if sendid not in sendid_2_res:
            sendid_2_res[sendid] = {}
        if uid not in sendid_2_res[sendid]:
            sendid_2_res[sendid][uid] = {}

        for region in region_quota:
            locations = user_conf['locations']
            if locations == '' or region in locations:
                quotaR , quotaK = filter_time(region, region_quota, user_conf)
                if len(quotaR) > 0 or len(quotaK) > 0:
                    sendid_2_res[sendid][uid][region] = {'quotaR': quotaR, 'quotaK': quotaK}

    return sendid_2_res

def format_res(region_res):
    result_str_list = []
    quotaR_prefix = '申领身份证时段'
    quotaK_prefix = '身份证旧换新时段'
    for region in region_res:
        quotaR_str = ''
        quotaK_str = ''
        result_str = ''
        if len(region_res[region]['quotaR']) > 0:
            quotaR_str = ', '.join(region_res[region]['quotaR'])
            result_str = quotaR_prefix + '\n' + quotaR_str + '\n'
        if len(region_res[region]['quotaK']) > 0:
            quotaK_str = ', '.join(region_res[region]['quotaK'])
            result_str += quotaK_prefix + '\n' + quotaK_str + '\n'

        result_str_list.append(region + '\n' + result_str)
    return result_str_list


def post_message(book_conf, sendid_2_res):
    json_temp = {"appToken":"AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB",
        "summary": "香港身份证预约信息,请尽快预约",
        "contentType": 1,
        "verifyPay": False,
    }
    headers = {"Content-Type": "application/json"}
    result_str_sep = '-----------\n'
    ts = int(time.time())

    for sendid in sendid_2_res:
        uid_str_list = []
        for uid in sendid_2_res[sendid]:
            # log_key = book_conf[uid]['log_key']
            log_record_list.append(book_conf[uid]['log_key'] + ":" + json.dumps(sendid_2_res[sendid][uid], ensure_ascii=False))
            result_str_list = format_res(sendid_2_res[sendid][uid])
            if len(result_str_list) > 0:
                uid_ts[uid] = ts + 750
                ori_uid = book_conf[uid]['ori_uid']
                if ori_uid != '-':
                    uid_str_list.append(uid + '\n' + '\n' + result_str_sep.join(result_str_list))
                else:
                    uid_str_list.append(result_str_sep.join(result_str_list))

        if len(uid_str_list) == 0:
            logger.info("%s: %s wechat message is empty" % (current_time_str, sendid))
            continue

        final_content = '请尽快预约防止被黄牛抢占\n============\n' + '============\n'.join(uid_str_list) + '\n============'
        json_temp['uids'] = [sendid]
        json_temp['content'] = final_content
        json_payload = json.dumps(json_temp)

        try:
            if sendid not in sendid_ts or sendid_ts[sendid] < ts:
                post_url = 'https://wxpusher.zjiecode.com/api/send/message'
                response_wx = requests.post(post_url, data=json_payload, headers=headers)
                logger.info("%s Send %s wechat success: %s" % (current_time_str, sendid, '\t'.join(log_record_list)))
            else:
                logger.info("%s %s is replicate output: %s" % (current_time_str, sendid, '\t'.join(log_record_list)))
        except Exception as e:
            logger.error('An error occurred: %s', str(e), exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    cnt = 0
    while True:
        book_conf = {}
        load_cnt = load_conf(book_conf)
        region_quota = get_http_request()
        log_record_list = [json.dumps(region_quota, ensure_ascii=False)]
        sendid_2_res = get_book_response(book_conf, region_quota)
        post_message(book_conf, sendid_2_res)
        cnt += 1
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.debug("%s run %d times, load_cnt: %u" % (current_time_str, cnt, load_cnt))
        time.sleep(10)
