import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import json
import time
from datetime import datetime


region_map = {"RHK": "湾仔", "RKO": "九龙", "RKT": "观塘", "FTO": "火炭", "TMO": "屯门", "YLO": "元朗"}
start_day = 20230501
end_day = 20231001
select_days = set([20230524, 20230525, 20230602, 20230603, 20230605, 20230609, 20230610])
# select_days = set([])

def parse_res(res):
    region_quota = {}
    for book in res['data']:
        date_time_fields = book['date'].split("/")
        date_time = int(date_time_fields[2] + date_time_fields[0] + date_time_fields[1])
        if date_time < start_day or date_time > end_day:
            continue
        office_id = region_map[book['officeId']]
        if office_id not in region_quota:
            region_quota[office_id] = {'quotaR' : [], 'quotaK': []}
        if book['quotaR'] != 'quota-r' and book['quotaR'] != 'quota-non':
            region_quota[office_id]['quotaR'].append(date_time)
        if book['quotaK'] != 'quota-r' and book['quotaK'] != 'quota-non':
            region_quota[office_id]['quotaK'].append(date_time)
    return region_quota

def get_http_request():
    url = "https://eservices.es2.immd.gov.hk/surgecontrolgate/ticket/getSituation"
    response = requests.get(url)
    region_quota = {}
    if response.status_code == 200:
        res = response.json()
        region_quota = parse_res(res)
    return region_quota


def send_email(result_str):
    sender = 'ynchen721@126.com'
    passwd = "7211248163264"
    receivers = ['yunan.chen@shopee.com']
    message = MIMEMultipart()
    message['From'] = sender
    message['To'] = ",".join(receivers)
    message['Subject'] = 'Quota_Reminder'
    text = MIMEText(result_str, 'plain')
    message.attach(text)
    with smtplib.SMTP('smtp.126.com', 25) as smtp:
        smtp.login(sender, passwd)
        smtp.sendmail(sender, receivers, message.as_string())


def filter_time(region, region_quota, key):
    name_map = {"quotaR": "一般服务时段", "quotaK": "延长服务时段"}
    valid_date = []
    for t in region_quota[region][key]:
        if t >= start_day and t <= end_day:
            if len(select_days) > 0:
                if t in select_days:
                    valid_date.append(str(t))
            else:
                valid_date.append(str(t))
    if len(valid_date) == 0:
        return ''
    return name_map[key] + '\n' + ','.join(valid_date)

result_str = ''
region_quota = get_http_request()
print(region_quota)
for region in region_quota:
    if region != region_map['RKO'] and region != region_map['TMO']:
        continue
    result_str_1 = filter_time(region, region_quota, 'quotaR')
    result_str_2 = filter_time(region, region_quota, 'quotaK')
    # result_str_2 = ''
    if result_str_1 != '' or result_str_2 != '':
        result_str += '\n'.join([region, result_str_1, result_str_2]) + '\n========================\n'

json_temp = {"appToken":"AT_7FOnGTv0fw0BSrAGDkVeEl2hJEjcBwwB",
        "summary": "Quota_reminder",
        "contentType": 1,
        "verifyPay": False,
        # "topicIds":[10054],
        "uids":['UID_DTNWzSlwh04rIEPWOiCJ4wPqcz4P'],
        "content": 'https://webapp.es2.immd.gov.hk/smartics2-client/QueueIt.html?applicationId=579&language=zh&country=HK\n========================\n' + result_str}

json_payload = json.dumps(json_temp)
headers = {"Content-Type": "application/json"}

if result_str != '':
    try:
        post_url = 'https://wxpusher.zjiecode.com/api/send/message'
        response_wx = requests.post(post_url, data=json_payload, headers=headers)
        send_email('https://webapp.es2.immd.gov.hk/smartics2-client/QueueIt.html?applicationId=579&language=zh&country=HK\n========================\n' + result_str)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(current_time + "\tsend_email success")
        print(region_quota)
        time.sleep(300)
    except:
        print("error occur")
else:
    print("result_str is empty")
