import requests
import fcntl
import threading
import time
import shutil
import json
from datetime import datetime as dt, timezone, timedelta, date
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import yaml
script_dir = os.path.dirname(os.path.abspath(__file__))
addition_path = os.path.join(script_dir, "trans_var.py")
sys.path.append(addition_path)
import trans_var
addition_path = os.path.join(script_dir, "book_candidate.py")
sys.path.append(addition_path)
from book_candidate import Candidate

def get_cur_time():
    sg_timezone = timezone(timedelta(hours=8), name='Asia/Singapore')
    singapore_time = dt.utcnow().replace(tzinfo=timezone.utc).astimezone(sg_timezone)
    cur_time = singapore_time.strftime('%H%M')
    return cur_time


def parse_select_days(book_conf):
    day_set = set(book_conf['select_days'].split(",")) if len(book_conf['select_days']) > 0 else set()
    exclude_day_set = set(book_conf['exclude_days'].split(",")) if len(book_conf['exclude_days']) > 0 else set()
    day_pairs = book_conf['day_intervals'].split(";") if len(book_conf['day_intervals']) > 0 else []
    if len(day_set) == 0 and len(day_pairs) == 0:
        current_date = date.today()
        future_date = current_date + timedelta(days=120)
        day_pairs = [current_date.strftime('%Y-%m-%d') + ',' + future_date.strftime('%Y-%m-%d')]

    if len(day_pairs) > 0:
        for day_pair in day_pairs:
            day1, day2 = day_pair.split(",")
            # 2023-01-01
            start_date = dt(int(day1[:4]), int(day1[5:7]), int(day1[8:]))
            end_date = dt(int(day2[:4]), int(day2[5:7]), int(day2[8:]))
            while start_date <= end_date:
                date_str = start_date.strftime("%Y-%m-%d")
                start_date += timedelta(days=1)
                if len(book_conf['weekdays']) > 0:
                    weekday, _ = trans_var.get_week_day(date_str)
                    if weekday not in book_conf['weekdays']:
                        continue
                day_set.add(date_str)
    return day_set - exclude_day_set

def init_book_conf():
    with open(trans_var.config_path, "r") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        total_book_conf = yaml.safe_load(open(trans_var.config_path))
        for id_name in total_book_conf:
            book_conf = total_book_conf[id_name]
            book_conf['time_intervals'] = book_conf['time_intervals'].split(",") if len(book_conf['time_intervals']) > 0 else []
            book_conf['office_ids'] = set(book_conf['office_ids'].split(",")) if len(book_conf['office_ids']) > 0 else set(trans_var.region_map.keys())
            book_conf['weekdays'] = set(book_conf['weekdays'].split(",")) if len(book_conf['weekdays']) > 0 else set()
            book_conf['select_days'] = parse_select_days(book_conf)
        return total_book_conf


def init_main_logger():
    log_path = trans_var.log_path_prefix + 'main'
    if os.path.exists(log_path):
        shutil.rmtree(log_path)
    os.makedirs(log_path)

    logger = logging.getLogger("main_logger")
    logger.setLevel(logging.DEBUG)
    handler = TimedRotatingFileHandler(log_path + '/hk_book.log', when='H', interval=3, backupCount=8)
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = init_main_logger()

def send_succ_message(id_name, book_conf, book_result):
    json_temp = {
        "appToken": "AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB",
        "summary": "身份证预约成功",
        "contentType": 1,
        "verifyPay": False,
        'uids': ['UID_DTNWzSlwh04rIEPWOiCJ4wPqcz4P'],
        'content': '\n'.join([id_name, book_conf['id_code'], book_conf['query_code'], book_result])
    }
    json_payload = json.dumps(json_temp)
    post_url = 'https://wxpusher.zjiecode.com/api/send/message'
    headers = {"Content-Type": "application/json"}
    try:
        response_wx = requests.post(post_url, data=json_payload, headers=headers)
    except Exception as e:
        logger.error('send wxpusher message failed: %s', str(e), exc_info=True)

def send_error_message(id_name):
    json_temp = {
        "appToken": "AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB",
        "summary": "以下用户异常",
        "contentType": 1,
        "verifyPay": False,
        'uids': ['UID_DTNWzSlwh04rIEPWOiCJ4wPqcz4P'],
        'content': id_name
    }
    json_payload = json.dumps(json_temp)
    post_url = 'https://wxpusher.zjiecode.com/api/send/message'
    headers = {"Content-Type": "application/json"}
    try:
        response_wx = requests.post(post_url, data=json_payload, headers=headers)
    except Exception as e:
        logger.error('send wxpusher message failed: %s', str(e), exc_info=True)

def run_query_program(candidate):
    while not candidate.stop_event.is_set():
        try_cnt = candidate.build_session()
        if try_cnt == 0 and len(candidate.book_res) == 0:
            send_error_message(candidate.id_name)
            time.sleep(600)
            continue

        while int(time.time()) - candidate.session_begin_time < 1100 and candidate.succ_flag != 1:
            candidate.multi_request_avail_date()
            candidate.filter_date(candidate.book_conf['select_days'])
            candidate.multi_req_avail_time()
            candidate.filter_region_time_v2(candidate.region_day_time)
            if len(candidate.cand_region_time) > 0:
                candidate.change_app_time()
            candidate.record_log()
            time.sleep(1)

        if candidate.succ_flag == 1:
            candidate.stop_event.is_set()

    if candidate.succ_flag == 0:
        candidate.delete_log()
    else:
        send_succ_message(candidate.id_name, candidate.book_conf, candidate.book_result)
        shutil.move(candidate.log_path, candidate.succ_log_path)
        candidate.record_succ_conf(trans_var.config_path)


def update_cand_info(cand_map, total_book_conf):
    delete_id_name = []
    for id_name in cand_map:
        candidate, _ = cand_map[id_name]
        if candidate.stop_event.is_set():
            delete_id_name.append(id_name)
        elif id_name not in total_book_conf or candidate.book_conf['version'] != total_book_conf[id_name]['version'] or total_book_conf[id_name]['suspend'] == 1:
            candidate.stop_event.set()
            delete_id_name.append(id_name)

    for id_name in delete_id_name:
        _, thd = cand_map[id_name]
        thd.join()
        del cand_map[id_name]

    for id_name in total_book_conf:
        if id_name not in cand_map and total_book_conf[id_name]['suspend'] == 0:
            c = Candidate(id_name, total_book_conf)
            thd = threading.Thread(target=run_query_program, args=(c,))
            cand_map[id_name] = (c, thd)
            thd.start()


if __name__ == "__main__":
    sentinal = trans_var.sentinal
    last_modified_time = 0
    cand_map = {}
    count = 0
    while True:
        current_modified_time = int(os.path.getmtime(trans_var.config_path))
        if current_modified_time > last_modified_time:
            logger.info("update conf because current_modified_time %u is larger than last_modified_time %u" % (current_modified_time, last_modified_time))
            last_modified_time = current_modified_time
            total_book_conf = init_book_conf()
            if len(total_book_conf) < 1:
                logger.error("Get book conf size is: " + str(len(total_book_conf)))
                sys.exit(2)
            update_cand_info(cand_map, total_book_conf)
        else:
            time.sleep(10)
        count += 1
        logger.info("run times: %u, conf_file_time: %u " % (count, current_modified_time))
