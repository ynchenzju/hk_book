import ddddocr
import json
import requests
from urllib import parse
import datetime
from urllib.parse import urlparse
import concurrent.futures
import os
import sys
import re
import time
import copy
script_dir = os.path.dirname(os.path.abspath(__file__))
trans_var_path = os.path.join(script_dir, "trans_var.py")
sys.path.append(trans_var_path)
import trans_var


class GenCand:
    def __init__(self, book_conf):
        enquiryCode = book_conf['query_code']
        book_type = book_conf['book_type']
        book_attr = trans_var.book_attr_map[book_type]
        groupSize = len(book_conf['applicant'])

        appl_avail_body = copy.deepcopy(trans_var.appl_avail_body)
        appl_avail_body['enquiryCode'] = enquiryCode
        appl_avail_body['natureGroup'] = book_attr['natureGroup']
        appl_avail_body['nature'] = book_attr['nature']
        appl_avail_body['groupSize'] = groupSize

        appt_body = copy.deepcopy(trans_var.req_make_appt_body)
        appt_body['enquiryCode'] = enquiryCode
        appt_body['natureGroup'] = book_attr['natureGroup']
        appt_body['nature'] = book_attr['nature']
        appt_body['groupSize'] = groupSize

        for applicant_info in book_conf['applicant']:
            id_code, birth_date = applicant_info.split(",")
            id_type = '2' if id_code[0] >= '0' and id_code[0] <= '9' else '1'
            id_postfix = id_code.split("(")[1].split(")")[0] if id_type == '1' else ''
            id_code = id_code.split("(")[0]

            birth_year = birth_date[:4]
            birth_day = birth_date[6:]
            appl_avail_body['applicants'].append(copy.deepcopy(trans_var.appl_struct))
            appl_avail_body['applicants'][-1]['identityType'] = id_type
            appl_avail_body['applicants'][-1]['identityNum'].append(id_code)
            if id_postfix != '':
                appl_avail_body['applicants'][-1]['identityNum'].append(id_postfix)

            appl_avail_body['applicants'][-1]['dateOfBirth'] = birth_year
            appl_avail_body['applicants'][-1]['yearOfBirth'] = birth_day
            appl_avail_body['applicants'][-1]['ageGroup'] = book_attr['ageGroup']

            appl_avail_body['checkDuplicateHkicDTOList'].append(copy.deepcopy(trans_var.checkDuplicateHkicDTO))
            appl_avail_body['checkDuplicateHkicDTOList'][-1]['hkic'] = id_code
            appl_avail_body['checkDuplicateHkicDTOList'][-1]['birthDateStr'] = birth_year + '01' + birth_day
            appl_avail_body['checkDuplicateHkicDTOList'][-1]['enquiryCode'] = enquiryCode
            appl_avail_body['checkDuplicateHkicDTOList'][-1]['identityType'] = id_type

            appt_body['applicantInfoDTOList'].append(copy.deepcopy(trans_var.applicantInfoDTO))
            appt_body['applicantInfoDTOList'][-1]['identityDocumentNum'] = id_type
            appt_body['applicantInfoDTOList'][-1]['identity'] = id_code
            appt_body['applicantInfoDTOList'][-1]['identityCode'] = id_postfix
            appt_body['applicantInfoDTOList'][-1]['dateOfBirth'] = birth_year + '01' + birth_day
            appt_body['applicantInfoDTOList'][-1]['ageGroup'] = book_attr['ageGroup']

        appt_body['applicants'] = appl_avail_body['applicants']
        self.appl_avail_body = appl_avail_body
        self.appt_body = appt_body


class Candidate:
    def __init__(self, id_name, bc_set, thd_index):
        self.book_conf = bc_set.book_conf
        self.id_name = id_name
        self.first_book = self.book_conf['first_book']
        self.normal_header = copy.deepcopy(trans_var.normal_header[thd_index % len(trans_var.normal_header)])
        self.session_begin_time = 0
        self.sess = None
        self.log_record_list = []
        self.cand_region_time = {}
        self.succ_flag = 0
        self.book_result = ''
        self.region_day_time = {}
        self.bc_set = bc_set
        self.logger = bc_set.logger
        self.thd_hint = "Thread " + str(thd_index) + " : "
        self.thd_index = thd_index

        if self.first_book:
            book_type = self.book_conf['book_type']
            self.book_attr = trans_var.book_attr_map[book_type]
            self.g = GenCand(self.book_conf)
            appl_avail_body_str = json.dumps(self.g.appl_avail_body, default=lambda x: None if x is None else x)
            appt_body_str = json.dumps(self.g.appt_body, default=lambda x: None if x is None else x)
            self.logger.info(self.thd_hint + 'create new cands: %s ||  %s' % (appl_avail_body_str, appt_body_str))
        else:
            self.rebook_body = copy.deepcopy(trans_var.rebook_body)
            id_code = self.book_conf['applicant'][0].split(",")[0].split("(")[0]
            self.rebook_body['identityCode'] = id_code
            self.rebook_body['identityType'] = '2' if id_code[0] >= '0' and id_code[0] <= '9' else '1'
            self.rebook_body['enquiryCode'] = self.book_conf['query_code']
            self.change_app_req = copy.deepcopy(trans_var.change_app_req)

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
                self.logger.warning(self.thd_hint + 'tc_times: %u get ticekt system is busy : %s' % tc_times)
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
            r = s.post(tc_link, data=json.dumps(tc_body, default=lambda x: None if x is None else x), headers=self.normal_header)
            while r.status_code != 200 and tc_times > 0:
                self.get_pic_code(s, tc_body)
                time.sleep(3)
                r = s.post(tc_link, data=json.dumps(tc_body, default=lambda x: None if x is None else x), headers=self.normal_header)
                self.logger.warning(self.thd_hint + "tc_times: %u res: %s, link: %s, result: %s" % (tc_times, tc_body['captchaCode'], tc_body['captchaId'], r.text))
                tc_times -= 1
            if r.status_code == 200:
                ret_code = trans_var.POST_SUCC
                self.book_res = {} if self.first_book else json.loads(r.text)
        except Exception as e:
            self.logger.error(self.thd_hint + 'tc_times: %u An error occurred in check_tcCaptcha : %s' % (tc_times, str(e)), exc_info=True)
            ret_code = trans_var.POST_ERROR

        return ret_code

    def build_session(self, sess_time_interval = 900):
        if int(time.time()) - self.session_begin_time < sess_time_interval and self.sess != None:
            return
        self.book_res = {}
        try_cnt_map = {"ip_check": 5, "get_ticket": 5, "tc_captcha": 5}
        ret_code = trans_var.POST_ERROR
        while ret_code == trans_var.POST_ERROR and try_cnt_map['ip_check'] > 0 and try_cnt_map['get_ticket'] > 0 and try_cnt_map['tc_captcha'] > 0:
            time.sleep(1)
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
                    self.logger.error(self.thd_hint + 'request checkip amazonaws failed, ip_check remains %u times' % try_cnt_map['ip_check'])
                    trans_var.renew_tor_ip()
                    continue

            ticketid, ticket_code = self.get_ticket_func()
            if ticket_code != trans_var.POST_SUCC:
                if ticket_code == trans_var.POST_ERROR:
                    try_cnt_map['get_ticket'] -= 1
                    trans_var.renew_tor_ip()
                self.logger.error(self.thd_hint + 'request get ticket failed code: %d, get_ticket remains %u times' % (ret_code, try_cnt_map['get_ticket']))
                continue
            self.session_begin_time = int(time.time())

            self.normal_header['ticketId'] = ticketid
            tc_body = self.g.appl_avail_body if self.first_book else self.rebook_body
            tc_link = trans_var.appl_avail_link if self.first_book else trans_var.book_enquiry_link
            ret_code = self.check_tcCaptcha(self.sess, tc_body, tc_link)
            try_cnt_map['tc_captcha'] -= 1
            if ret_code == trans_var.POST_ERROR:
                self.logger.error(self.thd_hint + 'request tc captcha failed, tc_captcha remains %u times' % try_cnt_map['tc_captcha'])
                trans_var.renew_tor_ip()

        self.logger.info(self.thd_hint + 'ret_code: %d out build session loop, try_cnt: %s' % (ret_code, json.dumps(try_cnt_map)))
        return ret_code


    def filter_region_time(self, region_day_time):
        self.cand_region_time = {}
        filter_by_certain_time = []
        for region in region_day_time:
            for daytime in region_day_time[region]:
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

        self.log_record_list.append('filter_by_certain_time: %s' % '|'.join(filter_by_certain_time))
        self.log_record_list.append('candidate_day_time: %s' % json.dumps(self.cand_region_time))

    def create_or_change_app(self):
        if self.first_book:
            self.create_appt()
        else:
            self.change_app_time()

    def create_appt(self):
        for region in self.cand_region_time:
            for avail_time in self.cand_region_time[region]:
                if len(avail_time['time_zone']) == 0:
                    continue
                self.g.appt_body['officeId'] = region
                self.g.appt_body['apptDate'] = avail_time['dt']
                self.g.appt_body['appointmentDate'] = ''.join(avail_time['dt'].split("-"))
                for time_zone in avail_time['time_zone']:
                    self.g.appt_body['appointmentTime'] = time_zone[0]
                    self.g.appt_body['appointmentEndTime'] = time_zone[1]
                    self.g.appt_body['startDate'] = time_zone[1]
                    r = self.sess.post(trans_var.req_make_appt_link,
                                       data=json.dumps(self.g.appt_body, default=lambda x: None if x is None else x),
                                       headers=self.normal_header)
                    self.book_result = "appDate:%s|appointmentTime:%s|officeId:%s" % (avail_time['dt'], time_zone[0], region)
                    if r.status_code == 200 and not self.bc_set.succ_event.is_set() and not self.bc_set.stop_event.is_set():
                        self.bc_set.succ_event.set()
                        self.bc_set.stop_event.set()
                        self.log_record_list.append(self.book_result + "|200")
                        self.succ_flag = 1
                        self.bc_set.book_result = self.book_result
                        break
                    else:
                        self.log_record_list.append(self.book_result + "|" + r.text + '|' + str(self.g.appt_body['applicants']))
                if self.succ_flag == 1:
                    break
            if self.succ_flag == 1:
                break

        self.log_record_list.append(json.dumps(self.g.appt_body))
        self.log_record_list.append(json.dumps(self.book_res))


    def change_app_time(self):
        self.change_app_req = copy.deepcopy(trans_var.change_app_req)
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
                    if r.status_code == 200 and not self.bc_set.succ_event.is_set() and not self.bc_set.stop_event.is_set():
                        self.bc_set.succ_event.set()
                        self.bc_set.stop_event.set()
                        self.log_record_list.append(self.book_result + "|200")
                        self.succ_flag = 1
                        self.bc_set.book_result = self.book_result
                        break
                    else:
                        self.log_record_list.append(self.book_result + "|" + r.text + '|' + str(self.change_app_req['changeSize']))
                if self.succ_flag == 1:
                    break
            if self.succ_flag == 1:
                break
        self.log_record_list.append(json.dumps(self.change_app_req))
        self.log_record_list.append(json.dumps(self.book_res))

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
            self.logger.error(self.thd_hint + '%s error occurred when http_req_avail_date: %s', region_en, str(e), exc_info=True)

        return {region_en: result}


    def fill_req_avail_date_body(self, new_req_avail_date_body):
        if self.first_book:
            new_req_avail_date_body['groupSize'] = str(len(self.book_conf['applicant']))
            new_req_avail_date_body['nature'] = self.book_attr['nature']
        else:
            new_req_avail_date_body['groupSize'] = str(self.book_res['applicantNum'])
            new_req_avail_date_body['nature'] = self.book_res['nature']

    def multi_request_avail_date(self):
        new_req_avail_date_body = copy.deepcopy(trans_var.req_avail_date_body)
        self.fill_req_avail_date_body(new_req_avail_date_body)

        self.region_day_time = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = []
            for region_en in self.book_conf['office_ids']:
                new_req_avail_date_body['targetOfficeId'] = region_en
                thread = executor.submit(self.http_req_avail_date, region_en, trans_var.req_date_link, copy.deepcopy(new_req_avail_date_body))
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
            self.logger.error(self.thd_hint + 'An error occurred in http_req_avail_time: %s', str(e), exc_info=True)

    def fill_req_avail_time_body(self, new_req_avail_time_body):
        if self.first_book:
            new_req_avail_time_body['groupSize'] = str(len(self.book_conf['applicant']))
            new_req_avail_time_body['nature'] = self.book_attr['nature']
        else:
            new_req_avail_time_body['groupSize'] = str(self.book_res['applicantNum'])
            new_req_avail_time_body['nature'] = self.book_res['nature']

    def multi_req_avail_time(self):
        new_req_avail_time_body = copy.deepcopy(trans_var.req_avail_time_body)
        self.fill_req_avail_time_body(new_req_avail_time_body)
        params = []
        for region in self.region_day_time:
            for daytime in self.region_day_time[region]:
                ts, dt = daytime['ts'], daytime['dt']
                new_req_avail_time_body['targetOfficeId'] = region
                new_req_avail_time_body['targetDate'] = dt
                params.append((trans_var.req_time_link, copy.deepcopy(new_req_avail_time_body), daytime))

        if len(params) > 0:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.map(lambda args: self.http_req_avail_time(*args), params)
                executor.shutdown(wait=True)

    def record_log(self):
        self.logger.info(self.thd_hint + '\t'.join(self.log_record_list))
        self.log_record_list = []

    def __del__(self):
        try:
            if self.sess is not None:
                self.sess.close()
        except:
            pass