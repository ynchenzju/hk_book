import requests
import fcntl
import time
import shutil
import json
from datetime import datetime as dt, timezone, timedelta, date
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
import concurrent.futures
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
    total_book_conf = yaml.safe_load(open(trans_var.config_path))
    all_select_days = set()
    for id_name in total_book_conf:
        book_conf = total_book_conf[id_name]
        book_conf['time_intervals'] = book_conf['time_intervals'].split(",") if len(book_conf['time_intervals']) > 0 else []
        book_conf['office_ids'] = set(book_conf['office_ids'].split(",")) if len(book_conf['office_ids']) > 0 else set()
        book_conf['weekdays'] = set(book_conf['weekdays'].split(",")) if len(book_conf['weekdays']) > 0 else set()
        book_conf['select_days'] = parse_select_days(book_conf)
        if id_name != trans_var.sentinal:
            all_select_days |= book_conf['select_days']
    return total_book_conf, all_select_days


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
        "summary": "香港身份证预约成功",
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


def run_query_program(candidate, region_day_time):
    candidate.filter_region_time(region_day_time)
    if len(candidate.cand_region_time) > 0:
        candidate.build_session()
        candidate.change_app_time()
        if candidate.succ_flag == 1:
            send_succ_message(candidate.id_name, candidate.book_conf, candidate.book_result)
    candidate.record_log()
    time_gap = 1800 if len(candidate.cand_region_time) > 0 else 3600
    candidate.build_session(time_gap)
    return candidate.id_name


def clear_cand_info(config_path, succ_id_name, cand_map):
    with open(config_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        tmp_book_conf = yaml.safe_load(open(config_path))
        for id_name in succ_id_name:
            shutil.move(cand_map[id_name].log_path, cand_map[id_name].succ_log_path)
            with open(cand_map[id_name].succ_config_path, 'w') as succ_yaml:
                yaml.dump({id_name: tmp_book_conf[id_name]}, succ_yaml)
            tmp_book_conf.pop(id_name)
            del cand_map[id_name]

        f.seek(0)
        f.truncate()
        yaml.dump(tmp_book_conf, f)

def update_cand_config(cand_map):
    total_book_conf, all_select_days = init_book_conf()
    for id_name in total_book_conf:
        if id_name in cand_map:
            cand_map[id_name].update_book_conf(id_name, total_book_conf)
        else:
            cand_map[id_name] = Candidate(id_name, total_book_conf)

    delete_id_name = []
    for id_name in cand_map:
        if id_name not in total_book_conf:
            if os.path.exists(cand_map[id_name].delete_log_path):
                shutil.rmtree(cand_map[id_name].delete_log_path)
            shutil.move(cand_map[id_name].log_path, cand_map[id_name].delete_log_path)
            delete_id_name.append(id_name)

    for id_name in delete_id_name:
        del cand_map[id_name]
    return total_book_conf, all_select_days


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
            total_book_conf, all_select_days = update_cand_config(cand_map)
            if len(all_select_days) == 0 or len(total_book_conf) <= 1:
                logger.error("Get book conf size is: " + str(len(total_book_conf)) + " all_select_day_size: " + str(len(all_select_days)))
                sys.exit(2)
        else:
            time.sleep(10)

        cand_map[sentinal].build_session()
        cand_map[sentinal].multi_request_avail_date()
        cand_map[sentinal].filter_date(all_select_days)
        cand_map[sentinal].multi_req_avail_time()
        cand_map[sentinal].record_log()
        succ_id_name = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = []
            for id_name in cand_map:
                if id_name == sentinal:
                    continue
                thread = executor.submit(run_query_program, cand_map[id_name], cand_map[sentinal].region_day_time)
                results.append(thread)

            for thread in concurrent.futures.as_completed(results):
                id_name = thread.result()
                if cand_map[id_name].succ_flag == 1:
                    succ_id_name.append(id_name)

        if len(succ_id_name) > 0:
            clear_cand_info(trans_var.config_path, succ_id_name, cand_map)
        count += 1
        logger.info("run times: %u, conf_file_time: %u, succ_id_name: %s " % (count, current_modified_time, " ".join(succ_id_name)))
