import requests
import time
import ddddocr
import re
from urllib import parse
from urllib.parse import urlparse
import json
import datetime
from datetime import datetime as dt, timezone, timedelta
import sys
import logging
import concurrent.futures
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
trans_var_path = os.path.join(script_dir, "slow_trans_var.py")
sys.path.append(trans_var_path)
from slow_trans_var import *

region_map = {"RHK": "湾仔", "RKO": "长沙湾", "RKT": "观塘", "FTO": "火炭", "TMO": "屯门", "YLO": "元朗"}
log_record_list = []

def get_cur_time():
    sg_timezone = timezone(timedelta(hours=8), name='Asia/Singapore')
    singapore_time = dt.utcnow().replace(tzinfo=timezone.utc).astimezone(sg_timezone)
    cur_time = singapore_time.strftime('%H%M')
    return cur_time

id_name = 'gan1'
if len(sys.argv) > 1:
    id_name = sys.argv[1]

def init_logger():
    logger = logging.getLogger('my_logger')
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    # handler = TimedRotatingFileHandler('./log/trans_hk.log', when='H', interval=3, backupCount=8)
    # handler.setLevel(logging.DEBUG)
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = init_logger()
book_conf = init_book_conf(id_name)

def get_ticketid(s):
    ticketid = ''
    try:
        r = s.get(NEW_TICKET_API)
        url = urlparse(r.url)
        query = url.query
        ticketid = parse.parse_qs(query).get('ticketId')[0]
    except Exception as e:
        logger.error('An error occurred in get_ticketid: %s', str(e), exc_info=True)
        ticketid = ''

    return ticketid


def get_pic(s):
    cap_refresh_api = 'https://webapp.es2.immd.gov.hk/smartics2-services/common-services/captcha_4_0_beta_3_5/botdetectcaptcha?get=html&c=tcCaptcha'
    r = s.get(cap_refresh_api, headers=normal_header)
    html = r.text
    capid = re.search(r'BDC_VCID_tcCaptcha" value="(\S*)"', html).group(1)
    rebook_body['captchaId'] = capid

    req_pic_api = 'https://webapp.es2.immd.gov.hk/smartics2-services/common-services/captcha_4_0_beta_3_5/botdetectcaptcha?get=image&c=tcCaptcha&t={}'.format(capid)
    r = s.get(req_pic_api, headers=normal_header)
    ocr = ddddocr.DdddOcr(show_ad = False)
    res = ocr.classification(r.content)

    return res

def check_tcCaptcha(s):
    book_res = {}
    try:
        try_tcCaptcha_cnt = 1
        rebook_body['captchaCode'] = get_pic(s)
        time.sleep(3)
        r = s.post("https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/bookingEnquiry/",
                   data=json.dumps(rebook_body), headers=normal_header)
        while r.status_code != 200:
            try_tcCaptcha_cnt += 1
            rebook_body['captchaCode'] = get_pic(s)
            time.sleep(3)
            r = s.post("https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/bookingEnquiry/",
                   data=json.dumps(rebook_body), headers=normal_header)
            logger.warning("try_tcCaptcha_cnt: %u, res: %s, link: %s, result: %s" % (try_tcCaptcha_cnt, rebook_body['captchaCode'], rebook_body['captchaId'], r.text))
        book_res = json.loads(r.text)
    except Exception as e:
        logger.error('An error occurred in check_tcCaptcha : %s', str(e), exc_info=True)

    return book_res

def http_req_avail_date(s, region_en, req_link, req_avail_date_body):
    result = []
    try:
        r = s.post(req_link, data=json.dumps(req_avail_date_body), headers=normal_header)
        if r.status_code == 200:
            raw_result = json.loads(r.text)
            for office_stat in raw_result['officeStatus']:
                if office_stat['status'] != 'A':
                    continue
                ts = int(office_stat['date'] / 1000)
                dt = datetime.date.fromtimestamp(ts)
                result.append({'ts': ts, 'dt': dt.strftime('%Y-%m-%d')})
    except Exception as e:
        logger.error('%s error occurred when http_req_avail_date: %s', region_en, str(e), exc_info=True)

    return {region_en: result}

def multi_request_avail_date(s, book_res):
    req_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestAvailDate/'
    req_avail_date_body = {
        "channel": "WEB",
        "svcId": "579",
        "appId": "579",
        "lang": "TC",
        "groupSize": int(book_res['applicantNum']),
        "targetOfficeId": "",
        "type": "make",
        "nature":book_res['nature']
    }

    avail_region_time = {}
    valid_regions = set(region_map.keys()) if len(book_conf['office_ids']) == 0 else book_conf['office_ids']

    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = []
        for region_en in valid_regions:
            req_avail_date_body['targetOfficeId'] = region_en
            thread = executor.submit(http_req_avail_date, s, region_en, req_link, req_avail_date_body.copy())
            results.append(thread)

        for thread in concurrent.futures.as_completed(results):
            result = thread.result()
            for key in result:
                if len(result[key]) > 0:
                    avail_region_time[key] = result[key]

    return avail_region_time


def request_avail_date(s, book_res):
    req_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestAvailDate/'
    req_avail_date_body = {
        "channel": "WEB",
        "svcId": "579",
        "appId": "579",
        "lang": "TC",
        "groupSize": int(book_res['applicantNum']),
        "targetOfficeId": "",
        "type": "make",
        "nature":book_res['nature']
    }

    avail_region_time = {}
    valid_regions = set(region_map.keys()) if len(book_conf['office_ids']) == 0 else book_conf['office_ids']

    for region_en in valid_regions:
        req_avail_date_body['targetOfficeId'] = region_en
        try:
            r = s.post(req_link, data = json.dumps(req_avail_date_body), headers=normal_header)
            if r.status_code == 200:
                raw_result = json.loads(r.text)
                for office_stat in raw_result['officeStatus']:
                    if office_stat['status'] != 'A':
                        continue
                    if region_en not in avail_region_time:
                        avail_region_time[region_en] = []
                    ts = int(office_stat['date'] / 1000)
                    dt = datetime.date.fromtimestamp(ts)
                    avail_region_time[region_en].append({'ts': ts, 'dt': dt.strftime('%Y-%m-%d')})
        except Exception as e:
            logger.error('An error occurred in request_avail_date: %s', str(e), exc_info=True)
    return avail_region_time


def req_avail_time(s, avail_region_time, book_res):
    req_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestAvailTime/'
    req_body = {
        "channel": "WEB",
        "svcId": "579",
        "appId": "579",
        "lang": "TC",
        "targetOfficeId": "",
        "targetDate": "",
        "filter": "",
        "groupSize": int(book_res['applicantNum']),
        "nature": book_res['nature'],
        "type": "make"
    }

    for region in avail_region_time:
        for daytime in avail_region_time[region]:
            ts, dt = daytime['ts'], daytime['dt']
            req_body['targetOfficeId'] = region
            req_body['targetDate'] = dt
            try:
                daytime['time_zone'] = []
                r = s.post(req_link, data=json.dumps(req_body), headers=normal_header)
                req_certen_times = json.loads(r.text)
                if 'timeZone' in req_certen_times:
                    for time_zone in req_certen_times['timeZone']:
                        daytime['time_zone'].append((time_zone['startTime'], time_zone['endTime']))
            except Exception as e:
                logger.error('An error occurred in req_avail_time: %s', str(e), exc_info=True)


def http_req_avail_time(s, req_link, req_body, daytime):
    try:
        daytime['time_zone'] = []
        r = s.post(req_link, data=json.dumps(req_body), headers=normal_header)
        req_certen_times = json.loads(r.text)
        if 'timeZone' in req_certen_times:
            for time_zone in req_certen_times['timeZone']:
                daytime['time_zone'].append((time_zone['startTime'], time_zone['endTime']))
    except Exception as e:
        logger.error('An error occurred in http_req_avail_time: %s', str(e), exc_info=True)


def multi_req_avail_time(s, avail_region_time, book_res):
    req_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestAvailTime/'
    req_body = {
        "channel": "WEB",
        "svcId": "579",
        "appId": "579",
        "lang": "TC",
        "targetOfficeId": "",
        "targetDate": "",
        "filter": "",
        "groupSize": int(book_res['applicantNum']),
        "nature": book_res['nature'],
        "type": "make"
    }
    with concurrent.futures.ThreadPoolExecutor() as executor:
        params = []
        for region in avail_region_time:
            for daytime in avail_region_time[region]:
                ts, dt = daytime['ts'], daytime['dt']
                req_body['targetOfficeId'] = region
                req_body['targetDate'] = dt
                params.append((s, req_link, req_body.copy(), daytime))
        executor.map(lambda args: http_req_avail_time(*args), params)
        executor.shutdown(wait=True)


def get_week_day(t):
    date_format = "%Y-%m-%d"
    date_object = datetime.datetime.strptime(t, date_format)
    weekday = date_object.weekday()
    weekday_str = date_object.strftime("%A")[:3]
    return str(weekday + 1), weekday_str


def change_app_time(s, book_res, valid_region_time):
    fill_change_app_req(book_res)
    succ_flag = 0
    req_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestChangeAppt/'
    book_result = ''
    for region in valid_region_time:
        for avail_time in valid_region_time[region]:
            if len(avail_time['time_zone']) == 0:
                continue
            change_app_req['officeId'] = region
            apptDate = avail_time['dt']
            appointmentDate = ''.join(apptDate.split("-"))
            for time_interval in avail_time['time_zone']:
                appointmentTime, appointmentEndTime = time_interval
                startDate = appointmentEndTime
                change_app_req['apptDate'] = apptDate
                change_app_req['appointmentDate'] = appointmentDate
                change_app_req['appointmentTime'] = appointmentTime
                change_app_req['appointmentEndTime'] = appointmentEndTime
                change_app_req['startDate'] = startDate
                r = s.post(req_link, data=json.dumps(change_app_req), headers=normal_header)
                book_result = "appDate:%s|appointmentTime:%s|officeId:%s" % (apptDate, appointmentTime, region)
                if r.status_code == 200:
                    log_record_list.append(book_result + "|200")
                    succ_flag = 1
                    break
                else:
                    log_record_list.append(book_result + "|" + r.text)
            if succ_flag == 1:
                break
        if succ_flag == 1:
            break
    return succ_flag, book_result


def send_succ_message(book_conf, book_result):
    json_temp = {
        "appToken": "AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB",
        "summary": "香港身份证预约成功",
        "contentType": 1,
        "verifyPay": False,
        'uids': [book_conf['sendid']],
        'content': '\n'.join([id_name, book_conf['id_code'], book_conf['query_code'], book_result])
    }
    json_payload = json.dumps(json_temp)
    post_url = 'https://wxpusher.zjiecode.com/api/send/message'
    headers = {"Content-Type": "application/json"}
    response_wx = requests.post(post_url, data=json_payload, headers=headers)

def filter_region_time(avail_region_time):
    valid_region_time = {}
    filter_by_certain_time = []

    for region in avail_region_time:
        for daytime in avail_region_time[region]:
            valid_time_zone = []
            if len(book_conf['time_intervals']) > 0:
                for book_time in daytime['time_zone']:
                    if book_time[0] < book_conf['time_intervals'][0] or book_time[0] > book_conf['time_intervals'][1]:
                        filter_by_certain_time.append(book_time[0])
                        continue
                    valid_time_zone.append(book_time)
            else:
                valid_time_zone = daytime['time_zone']

            if len(valid_time_zone) > 0:
                if region not in valid_region_time:
                    valid_region_time[region] = []
                valid_region_time[region].append({'ts': daytime['ts'], 'dt': daytime['dt'], 'time_zone': valid_time_zone})
    log_record_list.append('filter_by_certain_time: %s' % '|'.join(filter_by_certain_time))
    return valid_region_time

def filter_region_day(avail_region_time):
    filter_by_start_end = []
    filter_by_day_condition = []
    filter_by_weekday = []
    new_region_time = {}
    req_time_cnt = 0
    for region in avail_region_time:
        for daytime in avail_region_time[region]:
            dt = daytime['dt']
            if dt < book_conf['start_day'] or dt > book_conf['end_day']:
                filter_by_start_end.append(dt)
                continue

            continue_flag = True
            if len(book_conf['select_days']) == 0 and len(book_conf['day_intervals']) == 0:
                continue_flag = False
            if len(book_conf['select_days']) > 0 and dt in book_conf['select_days']:
                continue_flag = False
            if len(book_conf['day_intervals']) > 0 and dt >= book_conf['day_intervals'][0] and dt <= book_conf['day_intervals'][1]:
                continue_flag = False
            if continue_flag:
                filter_by_day_condition.append(dt)
                continue

            weekday, _ = get_week_day(dt)
            if len(book_conf['weekdays']) > 0 and weekday not in book_conf['weekdays']:
                filter_by_weekday.append(dt)
                continue

            if region not in new_region_time:
                new_region_time[region] = []
            new_region_time[region].append(daytime)
            req_time_cnt += 1

    log_record_list.append('filter_by_start_end: %s' % '|'.join(filter_by_start_end))
    log_record_list.append('filter_by_day_condition: %s' % '|'.join(filter_by_day_condition))
    log_record_list.append('filter_by_weekday: %s' % '|'.join(filter_by_weekday))
    return new_region_time, req_time_cnt

def run_query_program(s, book_res):
    raw_region_time = {}
    avail_region_time = {}
    valid_region_time = {}
    req_time_cnt = 0
    succ_flag = 0
    book_result = ''

    valid_regions = set(region_map.keys()) if len(book_conf['office_ids']) == 0 else book_conf['office_ids']
    if len(valid_regions) == 1:
        raw_region_time = request_avail_date(s, book_res)
    else:
        raw_region_time = multi_request_avail_date(s, book_res)

    if len(raw_region_time) > 0:
        avail_region_time, req_time_cnt = filter_region_day(raw_region_time)

    if len(avail_region_time) > 0:
        if req_time_cnt == 1:
            req_avail_time(s, avail_region_time, book_res)
        else:
            multi_req_avail_time(s, avail_region_time, book_res)
        valid_region_time = filter_region_time(avail_region_time)

    log_record_list.append(json.dumps(raw_region_time, ensure_ascii=False))
    log_record_list.append(json.dumps(avail_region_time, ensure_ascii=False))
    log_record_list.append(json.dumps(valid_region_time, ensure_ascii=False))

    if len(valid_region_time) > 0:
        pass
        # succ_flag, book_result = change_app_time(s, book_res, valid_region_time)

    return succ_flag, book_result


if __name__ == "__main__":
    if len(book_conf) == 0:
        logger.error("Get book conf size is: " + str(len(book_conf)))
        sys.exit(2)

    succ_flag = 0
    while True:
        cur_time = get_cur_time()
        if cur_time >= "0030" and cur_time <= "0830":
            logger.info("enter mid night and stop rob")
            sys.exit(1)

        succ_flag = 0
        s = requests.Session()
        ticketid = get_ticketid(s)
        if ticketid == '':
            s.close()
            time.sleep(10)

        normal_header['ticketId'] = ticketid
        book_res = check_tcCaptcha(s)
        if len(book_res) == 0:
            s.close()
            continue

        cur_ts = int(time.time())
        same_ticket_cnt = 1
        while int(time.time()) - cur_ts < 1150:
            succ_flag, book_result = run_query_program(s, book_res)
            logger.info("%s_%u: %s \t %u" % (ticketid, same_ticket_cnt, '\t'.join(log_record_list), succ_flag))
            log_record_list = []
            if succ_flag:
                send_succ_message(book_conf, book_result)
                break
            time.sleep(15)
            same_ticket_cnt += 1

        s.close()
        if succ_flag:
            break
        time.sleep(60)

    if succ_flag == 1:
        logger.info("get hk book successfully")
        sys.exit(0)
    else:
        logger.error("unknown condition")
        sys.exit(9)

