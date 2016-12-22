from __future__ import print_function
# provides support for Python 3.x style printing


"""
this sample demonstrates a simple custom skill built with the amazon alexa skills kit.
the intent schema, custom slots, and sample utterances for this skill, as well
as testing instructions are located at http://amzn.to/1LzFrj6

for additional samples, visit the alexa skills kit getting started guide:
http://amzn.to/1LGWsLG
"""


from datetime import datetime, time, date
import merakiapi
# snmp_helper functions courtesy of Kirk Byers: https://github.com/ktbyers/pynet/blob/master/snmp/snmp_helper.py
import snmp_helper
import requests
import json
import meraki_info
import re


"""
meraki_info.py is a simple definitions file containing private info that can be omitted from this file

example of meraki_info.py contents:
***
api_key = '<your api key>'
my_org_id = '<your org id>'
snmp_port = 16100
***
"""


# global variables used in the script
my_api_key = meraki_info.api_key
my_org_id = meraki_info.org_id
my_net_id = meraki_info.net_id
base_url = meraki_info.base_url
org_url = meraki_info.org_url
ssid_url = meraki_info.ssid_url
alexa_appid = meraki_info.alexa_appid
tropo_api_url = meraki_info.tropo_api_url
my_tropo_token = meraki_info.tropo_token
my_tropo_phone = meraki_info.tropo_phone
lic_url = meraki_info.lic_url
bind_url = meraki_info.bind_url
unbind_url = meraki_info.unbind_url
template_data = json.dumps(meraki_info.template_data)
community_string = meraki_info.community_string
snmp_port = meraki_info.snmp_port
headers = {'X-Cisco-Meraki-API-Key': my_api_key,
           'Content-Type': 'application/json'
           }
tropo_headers = {'accept': 'application/json',
                 'Content-Type': 'application/json'
                 }

# --------------- alexa skills kit provided functions ------------------
""" this section is included in the baseline custom skill sample.
the lines of code added below are for the 'intents' defined for this custom
skill. matching intents are defined for the skill under the alexa section at developer.amazon.com.
"""


def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    """
    the if statement prevents unauthorized use of your lambda function
    by requiring an application id match. the application id can be found at developer.amazon.com
    in the skill information fields of the custom skill.
    """
    if (event['session']['application']['applicationId'] !=
            str(alexa_appid)):
        raise ValueError("Invalid Application ID")

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])


def on_session_started(session_started_request, session):
    """ Called when the session starts """
    print("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """
    print("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # Dispatch to your skill's launch
    return get_welcome_response()


def on_intent(intent_request, session):
    """ Called when the user specifies an intent for this skill """
    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    # intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    """ Dispatch to your skill's intent handlers based on the 'intent_name'
    the Alexa service sends over. Example: If Alexa sends over an 'intent_name'
    of "GetStatus", that will call the 'get_network_status' function defined
    below.
    """
    # dashboard api - read the guest ssid pw and send it via sms using the tropo api
    if intent_name == "GetWiFiPw":
        return get_wifi_pw()
    # dashboard api - read license state
    elif intent_name == "GetLicense":
        return get_license_report()
    # snmp - snmp get oid for devStatus and respond with offline devices
    elif intent_name == "GetStatus":
        return get_network_status()
    # meraki easter egg
    elif intent_name == "GetRoadmap":
        return get_roadmap()
    # dashboard api - get device inventory and response with counts per-model type
    elif intent_name == "GetInventory":
        return get_inventory()
    # dashboard api - disable wifi, custom script - turn on tp-link hs100 smart plug
    elif intent_name == "CloseShop":
        return close_shop()
    # dashboard api - enable wifi, custom script - turn on tp-link hs100 smart plug
    elif intent_name == "OpenShop":
        return open_shop()
    # dashboard api - determine ap's broadcasting guest ssid and count clients
    elif intent_name == "GetGuestWifiUsers":
        return get_guest_count()
    elif intent_name == "AMAZON.HelpIntent":
        return get_welcome_response()
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.
    Is not called when the skill returns should_end_session=true
    """
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # add cleanup logic here


# --------------- alexa functions that control the skill's behavior ------------------


""" the fun stuff... the 'get_welcome_response' function below
is called when you say, "alexa, ask <my custom skill name>"
if you do not include a spoken intent, the 'get_welcome_response' function is called.
the custom skill name is defined at developer.amazon.com under the alexa section.
the 'speech_output' variable is what alexa ultimately responds with.
"""


def get_welcome_response():
    """ If we wanted to initialize the session to have some attributes we could
    add those here
    """
    session_attributes = {}
    card_title = "Welcome"
    speech_output = "Welcome to the Alexa Meraki Application. " \
                    "You can ask me for network status, inventory, " \
                    "and to open or close this shop. "
    # If the user either does not reply to the welcome message or says something
    # that is not understood, they will be prompted again with this text.
    reprompt_text = "Please ask me to do something like, " \
                    "what is the network status?"
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


# -------- Helper functions -------------- #
# including sample code provided by: Georg Prause & Rob Watt - https://github.com/meraki/provisioning-lib


# Filter IDs of org dictionary
def get_all_orgids():
    all_org_ids = []
    result = merakiapi.myorgaccess(my_api_key)
    for row in result:
        all_org_ids.append(row['id'])
    return all_org_ids


# Get the org-name
def get_orgname(id):
    """
    This function returns the name of a given org id
    """
    result = merakiapi.getorg(my_api_key, id)
    name = result['name']
    return name


# Get inventory and store models and their count in a dictionary
def get_org_inv_count():
    """
    This function uses requests to GET the org inventory, counts the model
    types, and writes them to a dictionary called org_inventory
    """
    # creates the dictionary called org_inventory to store key,value pairs
    org_inventory = {}
    result = merakiapi.getorginventory(my_api_key, my_org_id)
    for row in result:
        if row == 'errors':
            return 'errors'
        else:
            # iterate through the json response from the GET inventory
            """
            if the model (example:'MX65') does not already exist in the dictionary: 'org_inventory',
            set the value of org_inventory['MX65'] to 1 (for the first one). if 'MX65' is an existing
            key in 'org_inventory', then +1 the value (count) of org_inventory['MX65'].
            """
            if not row['model'] in org_inventory:
                org_inventory[(row['model'])] = 1
            else:
                org_inventory[(row['model'])] += 1
    return org_inventory


# Get network device inventory and create a list of MR's with the "guest_wireless" tag
def get_guest_ap_list():
    """
    This function uses requests to GET a network's devices and creates a list of MR's
    with the 'guest_wireless' device tag
    """
    # creates the dictionary called net_devices to store key,value pairs
    serial_list = []
    result = merakiapi.getnetworkdevices(my_api_key, my_net_id)
    for row in result:
        if row == 'errors':
            return 'errors'
        else:
            # iterate through the json response from the GET inventory
            guest_regex = re.compile('guest_wireless')
            m = guest_regex.search(str(row['tags']))
            model = row['model']
            if model[:2] == 'MR' and m is not None:
                serial_list.append(row['serial'])
            else:
                continue
    return serial_list

# Custom function for the nested dictionary encountered in the license report function
# nested key, values within a value
def nested(d):
    lic_dev = 0
    for k, v in d.iteritems():
        if k == 'expirationDate':
            exp_date = v
        elif k == 'licensedDeviceCounts':
            lic_list = v
            for y in lic_list.keys():
                if y == 'SM':
                    # only including hardware in this function
                    lic_list.pop(y)
            for z in lic_list.values():
                lic_dev += z
            return (lic_dev, exp_date)
        else:
            continue


# --------------- Meraki custom functions ------------------


# get the psk for a specific ssid
def get_ssid_psk():
    get_ssid_pw = merakiapi.getssiddetail(my_api_key, my_net_id, ssidnum=3)
    pw = get_ssid_pw['psk']
    return pw

# get the guest ssid pw and send to a tropo application to send the psk to 'my_tropo_phone' via sms
def get_wifi_pw():
    session_attributes = {}
    card_title = "WiFi Password SMS"
    # guest_pw = result of the get_wifi_pw function
    guest_pw = get_ssid_psk()

    # the data that will be passed in the POST to Tropo
    post_data = {"token": my_tropo_token,
                 "pw": guest_pw,
                 "number": my_tropo_phone
                 }
    # tropo_data = post_data jsonified
    tropo_data = json.dumps(post_data)

    # issue the post and print the http response code and response
    tropo_post = requests.post(tropo_api_url, headers=tropo_headers, data=tropo_data)
    if tropo_post.status_code == 200:
        speech_output = "OK"
    else:
        speech_output = "I'm sorry, there was an error"
    reprompt_text = ""
    should_end_session = True
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))

# get all org license state and read back organization names with license expiration < 90 days
def get_license_report():
    session_attributes = {}
    card_title = "License report"

    # Store the list of org id's in all_ids
    all_ids = get_all_orgids()

    date_format = "%b %d, %Y %Z"
    report_list = []

    # Loop through each org id to grab the name, license state, and device inventory
    for i in all_ids:
        org_name = get_orgname(i)
        lic = merakiapi.getlicensestate(my_api_key, i)
        lic_count = nested(lic)
        if lic_count[1] == 'N/A':
            continue
        else:
            a = datetime.strptime(lic_count[1], date_format)
            b = datetime.today()
            diff = a - b
            if 0 < diff.days < 90:
                speech_output = "{0} expires in {1} days".format(str(org_name), diff.days)
                report_list.append(speech_output)
            else:
                continue

    if not report_list:
        speech_output = "No license issues to report"

    reprompt_text = ""
    should_end_session = True
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


# Get the devName and devStatus SNMP OIDs and respond with the names of offline devices
def get_network_status():
    """ Grabs network status (via SNMP for now) and creates the 'speech_output'
    """
    session_attributes = {}
    card_title = "Network Status"
    # creating a few lists to write things to
    keys = []
    values = []
    list_offline = []
    # community_string and snmp_port are set under global variables
    device = ('snmp.meraki.com', community_string, snmp_port)
    # snmp_data1 is the list of devNames in the SNMP get response
    # snmp_helper is imported on line 25, see snmp_helper.py in the example
    snmp_data1 = snmp_helper.snmp_get_oid(device, oid='.1.3.6.1.4.1.29671.1.1.4.1.2', display_errors=True)
    # snmp_data2 is the 0 or 1 value that comes back from this OID indicating
    # the device's online/offline status (0 = offline, 1 = online)
    snmp_data2 = snmp_helper.snmp_get_oid(device, oid='.1.3.6.1.4.1.29671.1.1.4.1.3', display_errors=True)

    """
    create a dictionary of device names and their online/offline status.
    the following lines clean up the snmp responses in snmp_data1 and
    snmp_data2 individually, then add the sanitized data points to
    dict_status (snmp 'devName' and '0' or '1' for the status)
    """
    for i in snmp_data1:
        k = snmp_helper.snmp_extract(i)
        keys.append(k)
    for j in snmp_data2:
        m = snmp_helper.snmp_extract(j)
        values.append(m)
    # create a new dictionary 'dict_status' with the combined name and status
    dict_status = dict(zip(keys, values))
    # Now iterate through dict_status to capture offline devices
    for key in dict_status:
        value = dict_status[key]
        if value == '0':
            # below, 'devName' of offline devices (devStatus = 0) is appended to list_offline
            list_offline.append(key)
        else:
            # skip over devices which are not offline (any value other than 0)
            continue
    # Finally, count the length of 'list_offline' to get the number of offline
    # devices and read back each name in the list.
    # The extra spaces around the comma help Alexa read the names back clearly.
    # Adjustments may need to be made to fine tune the response.
    speech_output = "{0} devices are offline, {1}. would you like me to dispatch a technician ?".format(
                    len(list_offline), " , ".join(list_offline))
    reprompt_text = ""
    should_end_session = True
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


# grabs inventory and creates a reply for the user
def get_inventory():
    session_attributes = {}
    card_title = "Inventory"
    # Create a new list of model names and their count in inventory
    speech_list = []
    # get the org name
    org_name = get_orgname(my_org_id)
    # get device inventory and counts per-model
    inv = get_org_inv_count()
    # Loop through the inventory and create a list of device models and their
    # respective count to use in 'speech_output'
    for k, v in inv.iteritems():
        model_name = k
        dev_count = v
        speech_text = "{0} , {1}".format(str(model_name), dev_count)
        speech_list.append(str(speech_text))
    speech_output = "{0} - device inventory, {1}".format(str(org_name), speech_list)
    reprompt_text = ""
    should_end_session = True
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def close_shop():
    """ Disables the Guest SSID. Additional smart home functions could easily be added
    to turn off lights, lock doors, set a security alarm, set an away thermostat setting
    as examples...
    """
    session_attributes = {}
    card_title = "Close the shop"
    payload = json.dumps({ "enabled" : 'false' })
    off = requests.put(ssid_url, data=payload, headers=headers)
    print(off)
    if off.status_code == 200:
        speech_output = "Success ! Disabling guest wi-fi"
    else:
        speech_output = "Unsuccessful"
    reprompt_text = ""
    should_end_session = True
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


# enables the guest ssid
def open_shop():
    session_attributes = {}
    card_title = "Open the shop"
    payload = json.dumps({"enabled": 'true'})
    on = requests.put(ssid_url, data=payload, headers=headers)
    print(on)
    if on.status_code == 200:
        speech_output = "Success ! Enabling guest wi-fi"
    else:
        speech_output = "Unsuccessful"
    reprompt_text = ""
    should_end_session = True
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


# create a list of MR's with the "guest" tag and count clients on the guest ip subnet
def get_guest_count():
    session_attributes = {}
    card_title = "Guest WiFi User Count"
    sn_list = get_guest_ap_list()
    client_count = 0
    for sn in sn_list:
        result = merakiapi.getclients(my_api_key, sn, timestamp=900)
        for row in result:
            subnet_regex = re.compile('10.4.17')
            match = subnet_regex.search(str(row['ip']))
            if match is not None:
                client_count += 1
            else:
                continue

    speech_output = "There are {0} users on the guest wifi".format(client_count)
    reprompt_text = ""
    should_end_session = True
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


# an easter egg for Merakians =)
def get_roadmap():
    session_attributes = {}
    card_title = "roadmap"
    speech_output = "The first rule of Meraki roadmaps, " \
                    "is we do not talk about Meraki roadmaps. "
    reprompt_text = ""
    should_end_session = True
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


# --------------- Helper functions that build the responses ----------------------


def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': 'SessionSpeechlet - ' + title,
            'content': 'SessionSpeechlet - ' + output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }
