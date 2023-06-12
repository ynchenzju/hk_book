import yaml
import os
from stem.control import Controller
from stem import Signal
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "slow_config.yaml")


# NEW_TICKET_API = "https://eservices.es2.immd.gov.hk/surgecontrolgate/ticket/getTicketGet?svcId=579&applicationId=579&language=zh&country=HK&qitq=b7c0412c-ed4b-4976-9a9c-b4991003a7be&qitp=0729de79-9798-4618-a9ef-849a2295def7&qitts=1684147349&qitc=immdiconsprod&qite=immdsm2&qitrt=Safetynet&qith=56565ff4500e9b86c9926c4813576d89"
NEW_TICKET_API = "https://eservices.es2.immd.gov.hk/surgecontrolgate/ticket/getTicketGet?svcId=579&applicationId=579&language=zh&country=HK&qitq=cda5611b-fd16-45a4-8b0d-614726067e65&qitp=8869b7c9-9396-43bc-8954-db9e4b916ff2&qitts=1685767999&qitc=immdiconsprod&qite=immdsm2&qitrt=Safetynet&qith=98fafbfc7b5444f708cd74c0308d26e1"
normal_header = {
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


def init_book_conf(id_name):
    total_book_conf = yaml.safe_load(open(config_path))
    book_conf = {}
    if id_name in total_book_conf:
        book_conf = total_book_conf[id_name]
        book_conf['select_days'] = set(book_conf['select_days'].split(",")) if len(book_conf['select_days']) > 0 else set()
        book_conf['time_intervals'] = book_conf['time_intervals'].split(",") if len(book_conf['time_intervals']) > 0 else []
        book_conf['day_intervals'] = book_conf['day_intervals'].split(",") if len(book_conf['day_intervals']) > 0 else []
        book_conf['office_ids'] = set(book_conf['office_ids'].split(",")) if len(book_conf['office_ids']) > 0 else set()
        book_conf['weekdays'] = set(book_conf['weekdays'].split(",")) if len(book_conf['weekdays']) > 0 else set()
        rebook_body['identityCode'] = book_conf['id_code']
        rebook_body['identityType'] = '2' if book_conf['id_code'] >= '0' and book_conf['id_code'] <= '9' else '1'
        rebook_body['enquiryCode'] = book_conf['query_code']
    return book_conf


def fill_change_app_req(book_res):
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
        change_app_req['applicants'].append(app_instance)
        change_app_req['applicants'][-1]['apmidType'] = applicant['apmidType']
        change_app_req['applicants'][-1]['apmidCode'] = applicant['apmidCode']
        change_app_req['applicants'][-1]['appDob'] = applicant['appDob']
        change_app_req['applicants'][-1]['groupMemId'] = applicant['groupMemId']
        change_app_req['applicants'][-1]['ageInd'] = applicant['ageInd']
        change_app_req['applicants'][-1]['prefilInd'] = applicant['prefilInd']
        change_app_req['applicant'].append(change_app_req['applicants'][-1])

def renew_tor_ip():
    with Controller.from_port(port=9051) as controller:
        controller.authenticate(password="mypassword")
        controller.signal(Signal.NEWNYM)