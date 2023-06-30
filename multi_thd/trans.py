import fcntl
import threading
import time
import shutil
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
addition_path = os.path.join(script_dir, "book_cand_set.py")
sys.path.append(addition_path)
from book_cand_set import BookCandSet

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
            book_conf['applicant'] = book_conf['applicant'].split(";") if len(book_conf['applicant']) > 0 else []
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

def run_query_program(book_cand_set):
    book_cand_set.init_cand_list()
    book_cand_set.wait_for_thd()

def update_cand_info(cand_map, total_book_conf):
    delete_id_name = []
    for id_name in cand_map:
        book_cand_set, _ = cand_map[id_name]
        if book_cand_set.stop_event.is_set():
            delete_id_name.append(id_name)
        elif id_name not in total_book_conf or book_cand_set.book_conf['version'] != total_book_conf[id_name]['version'] or total_book_conf[id_name]['suspend'] == 1:
            book_cand_set.stop_event.set()
            delete_id_name.append(id_name)

    for id_name in delete_id_name:
        _, thd = cand_map[id_name]
        thd.join()
        del cand_map[id_name]

    for id_name in total_book_conf:
        if id_name not in cand_map and total_book_conf[id_name]['suspend'] == 0:
            b = BookCandSet(id_name, total_book_conf)
            thd = threading.Thread(target=run_query_program, args=(b,), daemon=True)
            cand_map[id_name] = (b, thd)
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
                logger.info("Get book conf size is: " + str(len(total_book_conf)))
                sys.exit(0)
            update_cand_info(cand_map, total_book_conf)
        else:
            cur_time = get_cur_time()
            if cur_time >= "0030" and cur_time <= "0730":
                logger.info("enter mid night and stop rob")
                for id_name in cand_map:
                    c, thd = cand_map[id_name]
                    c.stop_event.set()
                    thd.join()
                break
            time.sleep(10)
        count += 1
        logger.info("run times: %u, conf_file_time: %u " % (count, current_modified_time))