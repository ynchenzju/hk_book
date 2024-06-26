import datetime
from stem.control import Controller
from stem import Signal
import os
import copy
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.yaml")

sentinal = 'sentinal'
thd_num_per_cand = 4

POST_ERROR = -1
POST_SUCC = 0
POST_MAX_NUM = 1

region_map = {"RHK": "湾仔", "RKO": "长沙湾", "RKT": "观塘", "FTO": "火炭", "TMO": "屯门", "YLO": "元朗"}

NEW_TICKET_API = "https://eservices.es2.immd.gov.hk/surgecontrolgate/ticket/getTicketGet?svcId=579&applicationId=579&language=zh&country=HK"

cap_refresh_api = 'https://webapp.es2.immd.gov.hk/smartics2-services/common-services/captcha_4_0_beta_3_5/botdetectcaptcha?get=html&c=tcCaptcha'
req_pic_api_prefix = 'https://webapp.es2.immd.gov.hk/smartics2-services/common-services/captcha_4_0_beta_3_5/botdetectcaptcha?get=image&c=tcCaptcha&t='
book_enquiry_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/bookingEnquiry/'
change_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestChangeAppt/'
req_date_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestAvailDate/'
req_time_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestAvailTime/'
log_path_prefix = "./log/"
succ_log_path_prefix = "./log/succ_"
delete_log_path_prefix = "./log/delete_"

normal_header_0 = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Cookie': 'EGIS_RID=.1; IMMD_RID=.1',
        'Host': 'webapp.es2.immd.gov.hk',
        'Referer': 'https://webapp.es2.immd.gov.hk/smartics2-client/ropbooking/zh-HK/eservices/ropChangeCancelAppointment/step1',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
        'content-type': 'application/json',
        'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': "macOs",
        'ticketId': ''
}

normal_header_1 = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Cookie': 'EGIS_RID=.2; IMMD_RID=.1',
        'Host': 'webapp.es2.immd.gov.hk',
        'Referer': 'https://webapp.es2.immd.gov.hk/smartics2-client/ropbooking/zh-HK/eservices/ropChangeCancelAppointment/step1',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.54',
        'content-type': 'application/json',
        'sec-ch-ua': '"Microsoft Edge";v="111", "Not(A:Brand";v="8", "Chromium";v="111"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': "macOs",
        'ticketId': ''
}

normal_header_2 = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Connection': 'keep-alive',
        'Cookie': 'EGIS_RID=.2; IMMD_RID=.1',
        'Host': 'webapp.es2.immd.gov.hk',
        'Referer': 'https://webapp.es2.immd.gov.hk/smartics2-client/ropbooking/zh-HK/eservices/ropChangeCancelAppointment/step1',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/114.0',
        'content-type': 'application/json',
        'ticketId': ''
}

normal_header_3 = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Cookie': 'EGIS_RID=.2; IMMD_RID=.1',
        'Host': 'webapp.es2.immd.gov.hk',
        'Referer': 'https://webapp.es2.immd.gov.hk/smartics2-client/ropbooking/zh-HK/eservices/ropChangeCancelAppointment/step1',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/114.0',
        'content-type': 'application/json',
        'ticketId': ''
}

normal_header = [normal_header_0, normal_header_1, normal_header_2, normal_header_3]

###===========================================

req_avail_date_body = {
    "channel": "WEB",
    "svcId": "579",
    "appId": "579",
    "lang": "TC",
    "groupSize": 0,
    "targetOfficeId": "",
    "type": "make",
    "nature": ''
}

req_avail_time_body = {
    "channel": "WEB",
    "svcId": "579",
    "appId": "579",
    "lang": "TC",
    "targetOfficeId": "",
    "targetDate": "",
    "filter": "",
    "groupSize": 0,
    "nature": '',
    "type": "make"
}

identity_type = {"hk_id": "1", "hk_passport": "2"}

rebook_body = {
    "channel": "WEB",
    "svcId": "579",
    "appId": "579",
    "lang": "TC",
    "checkReminder": False,
    "quotaType": "R",
    "actionType": "changeCancel",
    "identityType": '',
    "identityCode": '',
    "enquiryCode": '',
    "captchaCode": '',
    "captchaId": ''
}

change_mode = {1: 'S', 2: 'W', 3: 'W'}

change_app_req = {
    "channel": "WEB",
    "svcId": "579",
    "appId": "579",
    "lang": "TC",
    "ern": "",
    "trn": "",
    "nature": "",
    "groupSize": 0,
    "oriErn": "",
    "oriTrn": "",
    "originalgroupSize": 0,
    "enquiryCode": "",
    "changeSize": 0,
    "changMode": 'S',
    "acknowledgement": {
        "lang": "ZH",
        "platform": "MacIntel"
    },
    "applicants": [],
    "applicant": [],

    "officeId": "",
    "appointmentDate": "",
    "appointmentTime": "",
    "appointmentEndTime": "",
    "apptDate": "",
    "startDate": "",
}

app_instance = {
    "apmidType": "",
    "apmidCode": "",
    "appDob": "",
    "groupMemId": "",
    "ageInd": "",
    "prefilInd": "",
    "selected": True
}

####===========================================
# 成年人ageGroup='A', 未满11岁儿童为'J'
# 多个未满11岁儿童一般时间段换证, nature = J; 1个时为'G'
# 1个未满11岁儿童选择延长时间段换证，nature='O'
book_attr_map = {
    'other': {'natureGroup' : 'FIRST_REGISTRATION', 'nature': 'D'},
    'evisa': {'natureGroup': 'FIRST_REGISTRATION', 'nature': 'W'},
    'adult_hkid': {'natureGroup': 'SIDCC', 'nature': 'S'}, # 成人身份证旧换新
    'child_hkid': {'natureGroup': 'REPLACEMENT', 'nature': 'G'}, # 未满11岁1个儿童一般时间段换证
    'child_first': {'natureGroup': 'FIRST_REGISTRATION', 'nature': 'B'}  # 满11岁1个儿童首次申请
}

appl_struct = {
    "identityType": "2",
    "identityNum": [],
    "ARN": [None, None],
    "dateOfBirth": "16",
    "yearOfBirth": "1999",
    "ageGroup": "A"
}
checkDuplicateHkicDTO = {
    "arn": "",
    "identityType": "2",
    "hkic": "999997",
    "birthDateStr": "19990116",
    "enquiryCode": "0721"
}
applicantInfoDTO = {
    "arn": "",
    "identityDocumentNum": "2",
    "identity": "999999",
    "identityCode": "",
    "dateOfBirth": "19990116",
    "ageGroup": "A"
}

# natrure_group = ['FIRST_REGISTRATION', 'REPLACEMENT']
# nature = ['D', 'I']
# identity_type = ['2', '1']

appl_avail_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/checkApplAvail/'
appl_avail_body = {
  "channel": "WEB",
  "svcId": "579",
  "appId": "579",
  "lang": "TC",
  "natureGroup": '',
  "nature": '',
  "groupSize": '',
  "applicants": [],
  "enquiryCode": "",
  "captchaCode": "",
  "captchaId": "",
  "checkDuplicateHkicDTOList": []
}


req_make_appt_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestMakeAppt/'
req_make_appt_body = {
  "channel": "WEB",
  "svcId": "579",
  "appId": "579",
  "lang": "TC",
  "natureGroup": '',
  "nature": '',
  "groupSize": '',
  "applicants": [],
  "enquiryCode": "1999",
  "officeId": "RHK",
  "appointmentDate": "20230614",
  "appointmentTime": "1015",
  "appointmentEndTime": "1030",
  "contactType": "N",
  "contactInformation": "",
  "apptDate": "2023-06-14",
  "startDate": "1030",
  "commlang": "zh-HK",
  "applicantInfoDTOList": [],
  "acknowledgement": {
    "lang": "ZH",
    "platform": "MacIntel"
  }
}

def fill_change_app_req(change_app_req, book_res):
    group_size = int(book_res['applicantNum'])
    change_app_req['ern'] = book_res['ern']
    change_app_req['trn'] = book_res['trn']
    change_app_req['oriErn'] = book_res['ern']
    change_app_req['oriTrn'] = book_res['trn']
    change_app_req['nature'] = book_res['nature']
    change_app_req['groupSize'] = group_size
    change_app_req['originalgroupSize'] = group_size
    change_app_req['enquiryCode'] = book_res['enquiryCode']
    change_app_req['changeSize'] = group_size
    change_app_req['changMode'] = change_mode[group_size]

    for applicant in book_res['listAppointmentInfo']:
        change_app_req['applicants'].append(copy.deepcopy(app_instance))
        change_app_req['applicants'][-1]['apmidType'] = applicant['apmidType']
        change_app_req['applicants'][-1]['apmidCode'] = applicant['apmidCode']
        change_app_req['applicants'][-1]['appDob'] = applicant['appDob']
        change_app_req['applicants'][-1]['groupMemId'] = applicant['groupMemId']
        change_app_req['applicants'][-1]['ageInd'] = applicant['ageInd']
        change_app_req['applicants'][-1]['prefilInd'] = applicant['prefilInd']
    change_app_req['applicant'] = change_app_req['applicants']

def get_week_day(t):
    date_format = "%Y-%m-%d"
    date_object = datetime.datetime.strptime(t, date_format)
    weekday = date_object.weekday()
    weekday_str = date_object.strftime("%A")[:3]
    return str(weekday + 1), weekday_str

def renew_tor_ip():
    with Controller.from_port(port=9051) as controller:
        controller.authenticate(password="mypassword")
        controller.signal(Signal.NEWNYM)
