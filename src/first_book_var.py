
natrure_group = ['FIRST_REGISTRATION', 'REPLACEMENT']
nature = ['D', 'I']
identity_type = ['2', '1']

appl_avail_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/checkApplAvail/'
appl_avail_body = {
  "channel": "WEB",
  "svcId": "579",
  "appId": "579",
  "lang": "TC",
  "natureGroup": natrure_group[0],
  "nature": nature[0],
  "groupSize": 1,
  "applicants": [
    {
      "identityType": "2",
      "identityNum": [
        "999997"
      ],
      "ARN": [
        None,
        None
      ],
      "dateOfBirth": "16",
      "yearOfBirth": "1999",
      "ageGroup": "A"
    }
  ],
  "enquiryCode": "0721",
  "captchaCode": "",
  "captchaId": "",
  "checkDuplicateHkicDTOList": [
    {
      "arn": "",
      "identityType": "2",
      "hkic": "999997",
      "birthDateStr": "19990116",
      "enquiryCode": "0721"
    }
  ]
}


req_make_appt_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/requestMakeAppt/'
req_make_appt_body = {
  "channel": "WEB",
  "svcId": "579",
  "appId": "579",
  "lang": "TC",
  "natureGroup": natrure_group[0],
  "nature": nature[0],
  "groupSize": 1,
  "applicants": [
    {
      "identityType": "2",
      "identityNum": [
        "999999"
      ],
      "ARN": [
        None,
        None
      ],
      "dateOfBirth": "16",
      "yearOfBirth": "1999",
      "ageGroup": "A"
    }
  ],
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
  "applicantInfoDTOList": [
    {
      "arn": "",
      "identityDocumentNum": "2",
      "identity": "999999",
      "identityCode": "",
      "dateOfBirth": "19990116",
      "ageGroup": "A"
    }
  ],
  "acknowledgement": {
    "lang": "ZH",
    "platform": "MacIntel"
  }
}

confirm_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/ropbooking/rop/changeAppointmentConfirmationNew/'
confirm_body = {
  "channel": "WEB",
  "svcId": "579",
  "appId": "579",
  "lang": "TC",
  "trn": "5792306281005393",
  "enquiryCode": "1999",
  "apmidCode": "999999"
}

getTicket_link = 'https://webapp.es2.immd.gov.hk/smartics2-services/surgecontrol/ticket/getTicket'
svc_body = {
  "svcId": "579"
}

# req_make_appt_body = {
#   "channel": "WEB",
#   "svcId": "579",
#   "appId": "579",
#   "lang": "TC",
#   "natureGroup": "",
#   "nature": "",
#   "groupSize": 1,
#   "applicants": [
#     {
#       "identityType": "1",
#       "identityNum": [
#         "M263962",
#         "4"
#       ],
#       "dateOfBirth": "23",
#       "yearOfBirth": "1966",
#       "ageGroup": "A"
#     }
#   ],
#   "enquiryCode": "1966",
#   "officeId": "RHK",
#   "appointmentDate": "20230608",
#   "appointmentTime": "0830",
#   "appointmentEndTime": "0845",
#   "contactType": "N",
#   "contactInformation": "",
#   "apptDate": "2023-06-08",
#   "startDate": "0845",
#   "commlang": "zh-HK",
#   "applicantInfoDTOList": [
#     {
#       "identityDocumentNum": "1",
#       "identity": "M263962",
#       "identityCode": "4",
#       "dateOfBirth": "19660123",
#       "ageGroup": "A"
#     }
#   ],
#   "acknowledgement": {
#     "lang": "ZH",
#     "platform": "MacIntel"
#   }
# }