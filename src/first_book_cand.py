import ddddocr
import copy
import random
import json
import requests
from urllib import parse
import datetime
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
import copy

class FirstCand:
    def __init__(self, id_name = 'default'):
        self.normal_header = copy.deepcopy(trans_var.normal_header)
        self.init_logger('default')

    def update_book_conf(self, id_name, total_book_conf):
        self.book_conf = total_book_conf[id_name]
        self.rebook_body['identityCode'] = self.book_conf['id_code']
        self.rebook_body['identityType'] = '2' if self.book_conf['id_code'][0] >= '0' and self.book_conf['id_code'][0] <= '9' else '1'
        self.rebook_body['enquiryCode'] = self.book_conf['query_code']

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

    def build_session(self, sess_time_interval = 1150):
        if int(time.time()) - self.session_begin_time < sess_time_interval and self.sess != None:
            return

        try_cnt = 5
        max_tc_cnt = 5
        self.book_res = {}
        while try_cnt >= 0:
            try:
                self.sess = requests.Session()
                if sys.platform == 'linux':
                    self.sess.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
                    try:
                        response = self.sess.get('https://checkip.amazonaws.com')
                        ip_address = response.text.strip()
                        self.logger.info('The session ip address is: ' + ip_address)
                    except:
                        try_cnt -= 1
                        self.logger.error('request checkip amazonaws failed, try_cnt %u renew ip' % try_cnt)
                        self.sess.close()
                        if sys.platform == 'linux':
                            trans_var.renew_tor_ip()
                        time.sleep(1)
                        continue

                self.session_begin_time = int(time.time())
                r = self.sess.get(trans_var.NEW_TICKET_API)
                url = urlparse(r.url)
                query = url.query
                ticketid = parse.parse_qs(query).get('ticketId')[0]
                if ticketid != '':
                    self.normal_header['ticketId'] = ticketid
                    try_tc_cnt = self.check_tcCaptcha(self.sess)
                    if try_tc_cnt > max_tc_cnt and len(self.book_res) == 0:
                        try_cnt = 0
                        break
                else:
                    self.logger.error('the web ticketid is null, please check!!')
            except Exception as e:
                self.logger.error('An error occurred in get_ticketid or check_tcCaptcha: %s', str(e), exc_info=True)

            if len(self.book_res) > 0:
                break
            self.sess.close()
            if sys.platform == 'linux':
                trans_var.renew_tor_ip()
            try_cnt -= 1
            time.sleep(1)
        return try_cnt


    def get_pic(self, s, rebook_body):
        r = s.get(trans_var.cap_refresh_api, headers=self.normal_header)
        html = r.text
        capid = re.search(r'BDC_VCID_tcCaptcha" value="(\S*)"', html).group(1)
        rebook_body['captchaId'] = capid

        req_pic_api = trans_var.req_pic_api_prefix + capid
        r = s.get(req_pic_api, headers=self.normal_header)
        ocr = ddddocr.DdddOcr(show_ad=False)
        res = ocr.classification(r.content)
        return res

    def check_tcCaptcha(self, s, rebook_body = trans_var.rebook_body.copy(), tc_link = trans_var.book_enquiry_link):
        try:
            max_try_cnt = 5
            try_tcCaptcha_cnt = 1
            rebook_body['captchaCode'] = self.get_pic(s, rebook_body)
            time.sleep(3)
            r = s.post(tc_link, data=json.dumps(rebook_body, default=lambda x: None if x is None else x), headers=self.normal_header)
            while r.status_code != 200:
                try_tcCaptcha_cnt += 1
                rebook_body['captchaCode'] = self.get_pic(s, rebook_body)
                time.sleep(3)
                r = s.post(tc_link, data=json.dumps(rebook_body, default=lambda x: None if x is None else x), headers=self.normal_header)
                self.logger.warning("try_tcCaptcha_cnt: %u, res: %s, link: %s, result: %s" % (
                try_tcCaptcha_cnt, rebook_body['captchaCode'], rebook_body['captchaId'], r.text))
                if try_tcCaptcha_cnt > max_try_cnt:
                    break
            # self.book_res = json.loads(r.text)
            if try_tcCaptcha_cnt > max_try_cnt and r.status_code != 200:
                self.book_res = {}
        except Exception as e:
            self.logger.error('An error occurred in check_tcCaptcha : %s', str(e), exc_info=True)
            self.book_res = {}
        return r.status_code


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
                    dt = datetime.date.fromtimestamp(ts)
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
        cnt = 0
        for region in self.region_day_time:
            for daytime in self.region_day_time[region]:
                ts, dt = daytime['ts'], daytime['dt']
                new_req_avail_time_body['targetOfficeId'] = region
                new_req_avail_time_body['targetDate'] = dt
                params.append((trans_var.req_time_link, new_req_avail_time_body.copy(), daytime))
                cnt += 1
                if cnt > 1:
                    break

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


    def make_appl_avail_req(self, g):
        try_cnt = 5
        max_tc_cnt = 5
        ret_code = -1
        self.book_res = {}
        while try_cnt >= 0:
            try:
                self.sess = requests.Session()
                self.session_begin_time = int(time.time())
                r = self.sess.get(trans_var.NEW_TICKET_API)
                url = urlparse(r.url)
                query = url.query
                ticketid = parse.parse_qs(query).get('ticketId')[0]
                if ticketid != '':
                    self.normal_header['ticketId'] = ticketid
                    new_appl_avail_body = g.appl_avail_body.copy()
                    ret_code = self.check_tcCaptcha(self.sess, new_appl_avail_body, first_book_var.appl_avail_link)
                    if ret_code != 200:
                        try_cnt = 0
                        break
                else:
                    self.logger.error('the web ticketid is null, please check!!')
            except Exception as e:
                self.logger.error('An error occurred in get_ticketid or check_tcCaptcha: %s', str(e), exc_info=True)

            if ret_code == 200:
                break
            self.sess.close()
            if sys.platform == 'linux':
                trans_var.renew_tor_ip()
            try_cnt -= 1
            time.sleep(1)
        return try_cnt


    def __del__(self):
        try:
            if self.sess is not None:
                self.sess.close()
        except:
            pass

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

        confirm_body = copy.deepcopy(first_book_var.confirm_body)
        confirm_body['enquiryCode'] = enquiryCode
        confirm_body['apmidCode'] = id_code
        now = datetime.datetime.now()
        month_day = now.strftime("%m%d")
        confirm_body['trn'] = "57923" + month_day + "1005" + str(random.randint(100, 999))

        self.appl_avail_body = appl_avail_body
        self.appt_body = appt_body

def make_first_book(region, dt, time_zone):
    g = GenCand(region, dt, time_zone)
    c = FirstCand()
    c.make_appl_avail_req(g)
    c.make_appt(g)
    print(g.appt_body)



if __name__ == "__main__":
    g = GenCand()
    c = FirstCand()
    c.make_appl_avail_req(g)
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