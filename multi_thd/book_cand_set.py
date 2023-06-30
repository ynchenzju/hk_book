import requests
import fcntl
import threading
import time
import shutil
import json
import random
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


class BookCandSet:
    def __init__(self, id_name, total_book_conf, cand_num = trans_var.thd_num_per_cand):
        self.stop_event = threading.Event()
        self.succ_event = threading.Event()
        self.cand_thd_list = []
        self.init_logger(id_name)
        self.id_name = id_name
        self.book_conf = total_book_conf[id_name]
        self.cand_num = cand_num
        if 'thd_num' in self.book_conf:
            self.cand_num = self.book_conf['thd_num']

    def init_cand_list(self):
        for i in range(self.cand_num):
            c = Candidate(self.id_name, self, i)
            thd = threading.Thread(target=self.run_query_program, args=(c,), daemon=True)
            self.cand_thd_list.append((c, thd))
            thd.start()

    def wait_for_thd(self):
        for i in range(self.cand_num):
            self.cand_thd_list[i][1].join()

        if self.succ_event.is_set():
            self.send_succ_message(self.id_name, self.book_conf, self.book_result)
            shutil.move(self.log_path, self.succ_log_path)
            self.record_succ_conf(trans_var.config_path)
        else:
            self.delete_log()

    def delete_log(self):
        if os.path.exists(self.delete_log_path):
            shutil.rmtree(self.delete_log_path)
        shutil.move(self.log_path, self.delete_log_path)

    def record_succ_conf(self, config_path):
        with open(config_path, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            tmp_book_conf = yaml.safe_load(open(config_path))
            succ_config_path = self.succ_log_path + "/" + self.id_name + ".yaml"
            with open(succ_config_path, 'w') as succ_yaml:
                yaml.dump({self.id_name: tmp_book_conf[self.id_name]}, succ_yaml)
            del tmp_book_conf[self.id_name]

            f.seek(0)
            f.truncate()
            yaml.dump(tmp_book_conf, f)

    def run_query_program(self, candidate):
        sleep_time = random.randint(0, 3)
        time.sleep(sleep_time)
        while not self.stop_event.is_set():
            build_succ_flag = candidate.build_session()
            if build_succ_flag != trans_var.POST_SUCC:
                self.send_error_message(candidate.id_name)
                time.sleep(600)
                continue

            while int(time.time()) - candidate.session_begin_time < 1100 and candidate.succ_flag != 1 and not self.stop_event.is_set():
                candidate.multi_request_avail_date()
                candidate.filter_date()
                candidate.multi_req_avail_time()
                candidate.filter_region_time(candidate.region_day_time)
                if len(candidate.cand_region_time) > 0:
                    candidate.create_or_change_app()
                candidate.record_log()
                time.sleep(5)

    def init_logger(self, id_name):
        self.log_path = trans_var.log_path_prefix + id_name
        self.succ_log_path = trans_var.succ_log_path_prefix + id_name
        self.delete_log_path = trans_var.delete_log_path_prefix + id_name
        if os.path.exists(self.log_path):
            shutil.rmtree(self.log_path)
        if os.path.exists(self.succ_log_path):
            shutil.rmtree(self.succ_log_path)
        if os.path.exists(self.delete_log_path):
            shutil.rmtree(self.delete_log_path)
        os.makedirs(self.log_path)

        self.logger = logging.getLogger(id_name)
        self.logger.setLevel(logging.DEBUG)
        handler = TimedRotatingFileHandler(self.log_path + '/hk_book.log', when='H', interval=3, backupCount=8)
        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def send_succ_message(self, id_name, book_conf, book_result):
        json_temp = {
            "appToken": "AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB",
            "summary": "身份证预约成功",
            "contentType": 1,
            "verifyPay": False,
            'uids': ['UID_DTNWzSlwh04rIEPWOiCJ4wPqcz4P'],
            'content': '\n'.join([id_name, book_conf['applicant'][0], book_conf['query_code'], book_result])
        }
        json_payload = json.dumps(json_temp)
        post_url = 'https://wxpusher.zjiecode.com/api/send/message'
        headers = {"Content-Type": "application/json"}
        try:
            requests.post(post_url, data=json_payload, headers=headers)
        except Exception as e:
            self.logger.error('send wxpusher message failed: %s', str(e), exc_info=True)

    def send_error_message(self, id_name):
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
            requests.post(post_url, data=json_payload, headers=headers)
        except Exception as e:
            self.logger.error('send wxpusher message failed: %s', str(e), exc_info=True)