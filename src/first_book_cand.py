import ddddocr
import copy
import redis
import random
import json
import requests
from urllib import parse
from datetime import datetime as dt, timezone, timedelta, date
from urllib.parse import urlparse
import logging
from logging.handlers import TimedRotatingFileHandler
import concurrent.futures
import os
import sys
import shutil
import re
import time
script_dir = os.path.dirname(os.path.abspath(__file__))
trans_var_path = os.path.join(script_dir, "trans_var.py")
sys.path.append(trans_var_path)
import trans_var
import first_book_var

class GenCand:
    def __init__(self, region = 'RHK', dt = '2023-01-01', time_zone = ("0000", "0000")):
        random_year = str(random.randint(1985, 2005))
        random_day = str(random.randint(10, 31))
        enquiryCode = str(random.randint(1000, 9999))
        id_code = str(random.randint(100000, 999999))

        appl_avail_body = copy.deepcopy(first_book_var.appl_avail_body)
        appl_avail_body['applicants'][0]['identityNum'][0] = id_code
        appl_avail_body['applicants'][0]['dateOfBirth'] = random_day
        appl_avail_body['applicants'][0]['yearOfBirth'] = random_year
        appl_avail_body['enquiryCode'] = enquiryCode
        appl_avail_body['checkDuplicateHkicDTOList'][0]['hkic'] = id_code
        appl_avail_body['checkDuplicateHkicDTOList'][0]['birthDateStr'] = random_year + '01' + random_day
        appl_avail_body['checkDuplicateHkicDTOList'][0]['enquiryCode'] = enquiryCode

        appt_body = copy.deepcopy(first_book_var.req_make_appt_body)
        appt_body['applicants'] = appl_avail_body['applicants']
        appt_body['enquiryCode'] = enquiryCode
        appt_body['officeId'] = region
        appt_body['appointmentDate'] = ''.join(dt.split("-"))
        appt_body['appointmentTime'] = time_zone[0]
        appt_body['appointmentEndTime'] = time_zone[1]
        appt_body['apptDate'] = dt
        appt_body['startDate'] = time_zone[1]

        appt_body['applicantInfoDTOList'][0]['identity'] = id_code
        appt_body['applicantInfoDTOList'][0]['dateOfBirth'] = random_year + '01' + random_day

        self.appl_avail_body = appl_avail_body
        self.appt_body = appt_body

class FirstCand:
    redis_pool = redis.ConnectionPool(host='168.138.196.53', port=6379, db=1, password='chenyunan721', max_connections=128)

    def __init__(self, region = 'RHK', dt = '2023-01-01', time_zone = ("0000", "0000")):
        self.normal_header = copy.deepcopy(trans_var.normal_header)
        self.init_logger('default')
        self.g = GenCand(region, dt, time_zone)

    def parse_exclude_days(self, book_conf):
        office_ids = book_conf['office_ids'].split(",") if len(book_conf['office_ids']) > 0 else list(trans_var.region_map.keys())
        weekdays = set(book_conf['weekdays'].split(","))
        day_set = set()
        if len(book_conf['day_intervals']) > 0:
            day_pairs = book_conf['day_intervals'].split(";")
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
                        if weekday not in weekdays:
                            continue
                    day_set.add(date_str)
        if len(book_conf['select_days']) > 0:
            day_set |= set(book_conf['select_days'].split(","))
        if len(book_conf['exclude_days']) > 0:
            day_set -= set(book_conf['exclude_days'].split(","))

        exclude_days = set()
        for region in office_ids:
            for day in day_set:
                exclude_days.add(region + "|" + day)
        return exclude_days


    def get_invalid_region_day(self):
        all_exclude_days = set()
        try:
            with redis.Redis(connection_pool=FirstCand.redis_pool) as r:
                book_conf = {}
                if r.exists('book_conf'):
                    book_conf = json.loads(r.get('book_conf'))
                print(book_conf)
                for userid in book_conf:
                    all_exclude_days |= self.parse_exclude_days(book_conf[userid])
        except:
            pass
        return all_exclude_days

    def init_logger(self, id_name):
        self.log_path = trans_var.log_path_prefix + id_name
        self.succ_log_path = trans_var.succ_log_path_prefix + id_name
        self.delete_log_path = trans_var.delete_log_path_prefix + id_name
        if os.path.exists(self.log_path):
            shutil.rmtree(self.log_path)
        if os.path.exists(self.succ_log_path):
            shutil.rmtree(self.succ_log_path)
        os.makedirs(self.log_path)

        self.logger = logging.getLogger(id_name)
        self.logger.setLevel(logging.DEBUG)
        handler = TimedRotatingFileHandler(self.log_path + '/hk_book.log', when='H', interval=3, backupCount=8)
        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.thd_hint = ''

    def get_ticket_func(self):
        ticketid = ''
        ret_code = trans_var.POST_MAX_NUM
        try:
            tc_times = 1000
            while ticketid == '' and tc_times > 0:
                r = self.sess.get(trans_var.NEW_TICKET_API)
                url = urlparse(r.url)
                query = url.query
                ticketid_list = parse.parse_qs(query).get('ticketId')
                if ticketid_list is not None:
                    ticketid = ticketid_list[0]
                    ret_code = trans_var.POST_SUCC
                    break
                tc_times -= 1
                self.logger.warning(self.thd_hint + 'tc_times: %u get ticekt system is busy' % tc_times)
                time.sleep(3)
        except Exception as e:
            self.logger.error(self.thd_hint + 'An error occurred in get_ticket: %s', str(e), exc_info=True)
            ret_code = trans_var.POST_ERROR
        return ticketid, ret_code



    def get_pic_code(self, s, tc_body):
        r = s.get(trans_var.cap_refresh_api, headers=self.normal_header)
        html = r.text
        capid = re.search(r'BDC_VCID_tcCaptcha" value="(\S*)"', html).group(1)
        tc_body['captchaId'] = capid

        req_pic_api = trans_var.req_pic_api_prefix + capid
        r = s.get(req_pic_api, headers=self.normal_header)
        ocr = ddddocr.DdddOcr(show_ad=False)
        tc_body['captchaCode'] = ocr.classification(r.content)

    def check_tcCaptcha(self, s, tc_body, tc_link):
        ret_code = trans_var.POST_MAX_NUM
        tc_times = 5
        self.book_res = {}
        try:
            self.get_pic_code(s, tc_body)
            time.sleep(3)
            r = s.post(tc_link, data=json.dumps(tc_body, default=lambda x: None if x is None else x),
                       headers=self.normal_header)
            while r.status_code != 200 and tc_times > 0:
                self.get_pic_code(s, tc_body)
                time.sleep(3)
                r = s.post(tc_link, data=json.dumps(tc_body, default=lambda x: None if x is None else x),
                           headers=self.normal_header)
                self.logger.warning(self.thd_hint + "tc_times: %u res: %s, link: %s, result: %s" % (
                tc_times, tc_body['captchaCode'], tc_body['captchaId'], r.text))
                tc_times -= 1
            if r.status_code == 200:
                ret_code = trans_var.POST_SUCC
                self.book_res = {} if self.first_book else json.loads(r.text)
        except Exception as e:
            self.logger.error(
                self.thd_hint + 'tc_times: %u An error occurred in check_tcCaptcha : %s' % (tc_times, str(e)),
                exc_info=True)
            ret_code = trans_var.POST_ERROR

        return ret_code

    def build_session(self, sess_time_interval=900):
        if int(time.time()) - self.session_begin_time < sess_time_interval and self.sess != None:
            return
        self.book_res = {}
        try_cnt_map = {"ip_check": 5, "get_ticket": 5, "tc_captcha": 5}
        ret_code = trans_var.POST_ERROR
        while ret_code == trans_var.POST_ERROR and try_cnt_map['ip_check'] > 0 and try_cnt_map['get_ticket'] > 0 and try_cnt_map['tc_captcha'] > 0:
            self.logger.info(self.thd_hint + 'in build session loop, try_cnt: %s' % json.dumps(try_cnt_map))
            if self.sess is not None:
                self.sess.close()
            self.sess = requests.Session()

            if sys.platform == 'linux':
                self.sess.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
                try_cnt_map['ip_check'] -= 1
                try:
                    response = self.sess.get('https://checkip.amazonaws.com')
                    ip_address = response.text.strip()
                    self.logger.info(self.thd_hint + 'The session ip address is: ' + ip_address)
                except:
                    self.logger.error(
                        self.thd_hint + 'request checkip amazonaws failed, ip_check remains %u times' % try_cnt_map[
                            'ip_check'])
                    trans_var.renew_tor_ip()
                    continue

            ticketid, ticket_code = self.get_ticket_func()
            if ticket_code != trans_var.POST_SUCC:
                if ticket_code == trans_var.POST_ERROR:
                    try_cnt_map['get_ticket'] -= 1
                    if sys.platform == 'linux':
                        trans_var.renew_tor_ip()
                self.logger.error(self.thd_hint + 'request get ticket failed code: %d, get_ticket remains %u times' % (ret_code, try_cnt_map['get_ticket']))
                continue

            self.session_begin_time = int(time.time())

            self.normal_header['ticketId'] = ticketid
            tc_body = self.g.appl_avail_body
            tc_link = trans_var.appl_avail_link
            ret_code = self.check_tcCaptcha(self.sess, tc_body, tc_link)
            try_cnt_map['tc_captcha'] -= 1
            if ret_code == trans_var.POST_ERROR:
                self.logger.error(self.thd_hint + 'request tc captcha failed, tc_captcha remains %u times' % try_cnt_map['tc_captcha'])
                if sys.platform == 'linux':
                    trans_var.renew_tor_ip()

        self.logger.info(self.thd_hint + 'ret_code: %d out build session loop, try_cnt: %s' % (ret_code, json.dumps(try_cnt_map)))
        return ret_code

    def filter_region_time(self, region_day_time):
        self.cand_region_time = {}
        filter_by_day_condition = []
        filter_by_region = []
        filter_by_certain_time = []
        for region in region_day_time:
            if len(self.book_conf['office_ids']) != 0 and region not in self.book_conf['office_ids']:
                filter_by_region.append(region)
                continue

            for daytime in region_day_time[region]:
                dt = daytime['dt']
                if dt not in self.book_conf['select_days']:
                    filter_by_day_condition.append(dt)
                    continue

                valid_time_zone = []
                if len(self.book_conf['time_intervals']) > 0:
                    for book_time in daytime['time_zone']:
                        if book_time[0] < self.book_conf['time_intervals'][0] or book_time[0] > self.book_conf['time_intervals'][1]:
                            filter_by_certain_time.append(book_time[0])
                            continue
                        valid_time_zone.append(book_time)
                else:
                    valid_time_zone = daytime['time_zone']

                if len(valid_time_zone) > 0:
                    if region not in self.cand_region_time:
                        self.cand_region_time[region] = []
                    self.cand_region_time[region].append({'ts': daytime['ts'], 'dt': daytime['dt'], 'time_zone': valid_time_zone})

        self.log_record_list.append('region_day_time: %s' % json.dumps(region_day_time))
        self.log_record_list.append('filter_by_region: %s' % '|'.join(filter_by_region))
        self.log_record_list.append('filter_by_day_condition: %s' % '|'.join(filter_by_day_condition))
        self.log_record_list.append('filter_by_certain_time: %s' % '|'.join(filter_by_certain_time))
        self.log_record_list.append('candidate_day_time: %s' % json.dumps(self.cand_region_time))

    def change_app_time(self):
        self.change_app_req = trans_var.change_app_req.copy()
        trans_var.fill_change_app_req(self.change_app_req, self.book_res)
        for region in self.cand_region_time:
            for avail_time in self.cand_region_time[region]:
                if len(avail_time['time_zone']) == 0:
                    continue
                self.change_app_req['officeId'] = region
                apptDate = avail_time['dt']
                appointmentDate = ''.join(apptDate.split("-"))
                for time_interval in avail_time['time_zone']:
                    appointmentTime, appointmentEndTime = time_interval
                    startDate = appointmentEndTime
                    self.change_app_req['apptDate'] = apptDate
                    self.change_app_req['appointmentDate'] = appointmentDate
                    self.change_app_req['appointmentTime'] = appointmentTime
                    self.change_app_req['appointmentEndTime'] = appointmentEndTime
                    self.change_app_req['startDate'] = startDate
                    r = self.sess.post(trans_var.change_link, data=json.dumps(self.change_app_req), headers=self.normal_header)
                    self.book_result = "appDate:%s|appointmentTime:%s|officeId:%s" % (apptDate, appointmentTime, region)
                    if r.status_code == 200:
                        self.log_record_list.append(self.book_result + "|200")
                        self.succ_flag = 1
                        break
                    else:
                        self.log_record_list.append(self.book_result + "|" + r.text)
                if self.succ_flag == 1:
                    break
            if self.succ_flag == 1:
                break

    def http_req_avail_date(self, region_en, req_link, req_avail_date_body):
        result = []
        try:
            r = self.sess.post(req_link, data=json.dumps(req_avail_date_body), headers=self.normal_header)
            if r.status_code == 200:
                raw_result = json.loads(r.text)
                for office_stat in raw_result['officeStatus']:
                    if office_stat['status'] != 'A':
                        continue
                    ts = int(office_stat['date'] / 1000)
                    dt = date.fromtimestamp(ts)
                    result.append({'ts': ts, 'dt': dt.strftime('%Y-%m-%d')})
        except Exception as e:
            self.logger.error('%s error occurred when http_req_avail_date: %s', region_en, str(e), exc_info=True)

        return {region_en: result}

    def multi_request_avail_date(self):
        new_req_avail_date_body = trans_var.req_avail_date_body.copy()
        new_req_avail_date_body['groupSize'] = 1
        new_req_avail_date_body['nature'] = 'D'

        self.region_day_time = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = []
            for region_en in trans_var.region_map:
                new_req_avail_date_body['targetOfficeId'] = region_en
                thread = executor.submit(self.http_req_avail_date, region_en, trans_var.req_date_link, new_req_avail_date_body.copy())
                results.append(thread)

            for thread in concurrent.futures.as_completed(results):
                result = thread.result()
                for key in result:
                    if len(result[key]) > 0:
                        self.region_day_time[key] = result[key]


    def filter_date(self, all_select_days):
        new_region_time = {}
        for region in self.region_day_time:
            for daytime in self.region_day_time[region]:
                if daytime['dt'] in all_select_days:
                    if region not in new_region_time:
                        new_region_time[region] = []
                    new_region_time[region].append(daytime)
        self.old_region_day_time = self.region_day_time
        self.region_day_time = new_region_time
        self.log_record_list.append("total region_daytime is: " + json.dumps(self.old_region_day_time))
        self.log_record_list.append("valid region_daytime is: " + json.dumps(self.region_day_time))


    def http_req_avail_time(self, req_link, req_body, daytime):
        try:
            daytime['time_zone'] = []
            r = self.sess.post(req_link, data=json.dumps(req_body), headers=self.normal_header)
            req_certen_times = json.loads(r.text)
            if 'timeZone' in req_certen_times:
                for time_zone in req_certen_times['timeZone']:
                    daytime['time_zone'].append((time_zone['startTime'], time_zone['endTime']))
        except Exception as e:
            self.logger.error('An error occurred in http_req_avail_time: %s', str(e), exc_info=True)


    def multi_req_avail_time(self):
        new_req_avail_time_body = trans_var.req_avail_time_body.copy()
        new_req_avail_time_body['groupSize'] = 1
        new_req_avail_time_body['nature'] = 'D'
        params = []
        for region in self.region_day_time:
            for daytime in self.region_day_time[region]:
                ts, dt = daytime['ts'], daytime['dt']
                new_req_avail_time_body['targetOfficeId'] = region
                new_req_avail_time_body['targetDate'] = dt
                params.append((trans_var.req_time_link, new_req_avail_time_body.copy(), daytime))

        if len(params) > 0:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.map(lambda args: self.http_req_avail_time(*args), params)
                executor.shutdown(wait=True)

    def record_log(self):
        self.logger.info('\t'.join(self.log_record_list))
        self.log_record_list = []

    def make_appt(self, g):
        try:
            r = self.sess.post(first_book_var.req_make_appt_link, data=json.dumps(g.appt_body, default=lambda x: None if x is None else x), headers=self.normal_header)
            print(r.text)
            # {"trn":"5792306281005703","transactionDateTime":1687955583541,"errorCode":"","oriTrn":null}
        except:
            pass


    def __del__(self):
        try:
            if self.sess is not None:
                self.sess.close()
        except:
            pass

def make_first_book(region, dt, time_zone):
    c = FirstCand(region, dt, time_zone)
    c.make_appt()


if __name__ == "__main__":
    c = FirstCand()
    all_exclude_days = c.get_invalid_region_day()
    c.build_session()
    c.multi_request_avail_date()
    c.multi_req_avail_time()
    for region in c.region_day_time:
        daytime = c.region_day_time[region][0]
        flag = 0
        for time_zone in daytime['time_zone']:
            make_first_book(region, daytime['dt'], time_zone)
            flag = 1
            break
        if flag:
            break

    # 241930 7559
    # 731906 3930