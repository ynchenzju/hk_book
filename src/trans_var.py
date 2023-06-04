import yaml
import datetime
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.yaml")

region_map = {"RHK": "湾仔", "RKO": "长沙湾", "RKT": "观塘", "FTO": "火炭", "TMO": "屯门", "YLO": "元朗"}

NEW_TICKET_API = "https://eservices.es2.immd.gov.hk/surgecontrolgate/ticket/getTicketGet?svcId=579&applicationId=579&language=zh&country=HK&qitq=b7c0412c-ed4b-4976-9a9c-b4991003a7be&qitp=0729de79-9798-4618-a9ef-849a2295def7&qitts=1684147349&qitc=immdiconsprod&qite=immdsm2&qitrt=Safetynet&qith=56565ff4500e9b86c9926c4813576d89"
cap_refresh_api = 'https://webapp.es2.immd.gov.hk/smartics2-services/common-services/captcha_4_0_beta_3_5/botdetectcaptcha?get=html&c=tcCaptcha'
req_pic_api_prefix = 'https://webapp.es2.immd.gov.hk/smartics2-services/common-services/captcha_4_0_beta_3_5/botdetectcaptcha?get=image&c=tcCaptcha&t='
book_enquiry_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/bookingEnquiry/'
change_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestChangeAppt/'
req_date_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestAvailDate/'
req_time_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestAvailTime/'
log_path_prefix = "./log/"
succ_log_path_prefix = "./log/succ_"
delete_log_path_prefix = "./log/delete_"

normal_header = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Cookie': 'EGIS_RID=.1; IMMD_RID=.2',
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
        change_app_req['applicants'].append(app_instance.copy())
        change_app_req['applicants'][-1]['apmidType'] = applicant['apmidType']
        change_app_req['applicants'][-1]['apmidCode'] = applicant['apmidCode']
        change_app_req['applicants'][-1]['appDob'] = applicant['appDob']
        change_app_req['applicants'][-1]['groupMemId'] = applicant['groupMemId']
        change_app_req['applicants'][-1]['ageInd'] = applicant['ageInd']
        change_app_req['applicants'][-1]['prefilInd'] = applicant['prefilInd']
        change_app_req['applicant'].append(change_app_req['applicants'][-1])

def get_week_day(t):
    date_format = "%Y-%m-%d"
    date_object = datetime.datetime.strptime(t, date_format)
    weekday = date_object.weekday()
    weekday_str = date_object.strftime("%A")[:3]
    return str(weekday + 1), weekday_str