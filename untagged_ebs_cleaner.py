"""
    This module will tag untagged and unattached volumes with tag
    TTL = 6

    Obeys the TTL tag for Instances, but each resource has to be tagged in order
     to
    prevent deletion. The deletion of EBS volume would happen 6 days after
    they receive the tag TTL.

    Specifics:
        1. A JIRA ticket would be raised on day 1 or Monday.:
            - the ticket would be updated on Thursday and Saturday
            - no backup would be  preformed
                set upped at the time of instance creation.
"""
import datetime as dt
import json
import logging
from os import environ
import urllib3
from dateutil.relativedelta import relativedelta
import boto3
JIRA_URL = environ['JIRA_SERVICEDESK_URL']
JIRA_USER = environ['JIRA_SERVICEDESK_USER']

DOMAIN = environ['DOMAIN']

FIRST_NOTIFICATION_AFTER_M_DAYS = environ['FIRST_NOTIFICATION_DAYS']
SECOND_NOTIFICATION_AFTER_N_DAYS = environ['SECOND_NOTIFICATION_DAYS']
DELETION_AFTER_N_DAYS: str = environ['DELETION_AFTER_DAYS']

EC2 = boto3.client('ec2')
SSM = boto3.client('ssm')

SD = environ["SD"]
PERIOD = int(environ["PERIOD"])
PREFIX = environ["PREFIX"]

INITIAL_DATE = f"/{PREFIX}/initial_date"
TICKET_ID = f"/{PREFIX}/ticket_id"
JIRA_TOKEN = SSM.get_parameter(Name=environ['JIRA_TOKEN'],
                               WithDecryption=True)['Parameter']['Value']

def lambda_handler(event, context):
    """
            Summary: initial function which calls the needed modules defined
                    in the supplied configuration

            Parameters:
                :param event: dict - the supplied configuration when the Lambda
                is invoked.
                :param context: obj - not used, context of the invocation
        """
    description = ""
    account_id = context.invoked_function_arn.split(":")[4]
    scheduled_for_deletion_ebs = get_unattached_volumes()
    print(scheduled_for_deletion_ebs)
    today = dt.date.today()
    deletion_information = ""
    deletion_date = today + relativedelta(days=int(DELETION_AFTER_N_DAYS))
    for ebs in scheduled_for_deletion_ebs:

        if ebs['TTL'] == '0':
            description += '''Untagged EBS volume with id {0[id]} in account
            {1}, status {0[status]}, size {0[size]} will be deleted on {2}
            at 0:00 UTC\n'''.format(ebs, account_id, deletion_date)
        else:
            description += '''Untagged EBS volume in account {1} with id
             {0[id]}, status {0[status]}, size {0[size]} will be deleted after
             {0[TTL]} on {2}. Please tag the volume, if the deletion is
              unwanted\n'''.format(ebs, account_id, deletion_date)

        print(description)
    ssm_param = ''
    try:
        ssm_param = \
            SSM.get_parameter(Name=INITIAL_DATE)['Parameter'][
                'Value']
    except SSM.exceptions.ParameterNotFound as e_not_present:
        print(e_not_present)
    if not ssm_param and description:

        ticket_id = open_jira_ticket(description, 'Service Request')
        SSM.put_parameter(Name=TICKET_ID,
                          Description="Ticket number in jira",
                          Value=str(ticket_id),
                          Type="String",
                          Overwrite=True)
        SSM.put_parameter(Name=INITIAL_DATE,
                          Description="Initial Date",
                          Value=str(today),
                          Type="String",
                          Overwrite=True)

    elif ssm_param and dt.datetime.strptime(ssm_param, '%Y-%m-%d').date() + \
        relativedelta(days=int(FIRST_NOTIFICATION_AFTER_M_DAYS)) == today or \
            dt.datetime.strptime(ssm_param, '%Y-%m-%d').date() + \
            relativedelta(days=int(SECOND_NOTIFICATION_AFTER_N_DAYS)) == today:
        try:
            reminder = "\nA KIND REMINDER!\n" + description
            response = SSM.get_parameter(Name=TICKET_ID, WithDecryption=True)
            update_jira_ticket(response['Parameter']['Value'], reminder)
        except Exception as e_not_present:
            logging.error("retrieve param error: %s", e_not_present)
            raise e_not_present
    elif dt.datetime.strptime(ssm_param, '%Y-%m-%d').date() + \
            relativedelta(days=int(DELETION_AFTER_N_DAYS)) == today:
        response = SSM.get_parameter(Name=TICKET_ID, WithDecryption=True)
        for ebs in scheduled_for_deletion_ebs:
            if ebs['TTL'] == '0':
                deletion_date = today
                EC2.delete_volume(VolumeId=ebs['id'])
                deletion_information += '''UNTAGGED EBS VOLUME IN ACCOUNT {1}
                WITH ID {0[id]}, STATUS {0[status]}, SIZE {0[size]}
                WAS DELETED ON {2}.\n'''.format(ebs, account_id, deletion_date)
        update_jira_ticket(response['Parameter']['Value'],
                           deletion_information)
        SSM.delete_parameter(Name=TICKET_ID)
        SSM.delete_parameter(Name=INITIAL_DATE)


def get_unattached_volumes():
    """
        Summary: Function to filter and describe in json untagged volumes
        Parameters: N/A
    """
    scheduled_for_deletion_ebs = []
    for volume in EC2.describe_volumes(Filters=[{
            'Name': 'status',
            'Values': ['available']
    }])['Volumes']:
        values = {
            'id': volume['VolumeId'],
            'status': volume['State'],
            'size': volume['Size']
        }

        if 'Tags' not in volume:
            EC2.create_tags(Resources=[values['id']],
                            Tags=[{
                                'Key': 'TTL',
                                'Value': DELETION_AFTER_N_DAYS
                            }])
            values['TTL'] = DELETION_AFTER_N_DAYS
        else:
            value = [
                tag['Value'] for tag in volume['Tags'] if tag['Key'] == 'TTL'
            ]
            if int(value[0]) > 0:
                counter = int(value[0])
                counter -= PERIOD
                values['TTL'] = str(counter)
                EC2.create_tags(Resources=[values['id']],
                                Tags=[{
                                    'Key': 'TTL',
                                    'Value': str(counter)
                                }])
                print(len(volume['Tags']))
            else:
                values['TTL'] = '0'
        scheduled_for_deletion_ebs.append(values)
    return scheduled_for_deletion_ebs


def open_jira_ticket(ticket_description, issue_type):
    """
        Summary: Open jira ticket function

        Parameters:
            :param ticket_description: str - creates the main description and
            purpose of the ticket
            :param issue_type: str - ticket type could be service request,change
             request, incident or task
    """
    http = urllib3.PoolManager()
    resource_name = 'issue'
    search_api = JIRA_URL + f'/rest/api/latest/{resource_name}/'
    task_summary = f'Automated detection and deletion or orhpaned, ' \
                   f'untagged EBS volumes'
    headers = urllib3.util.make_headers(
        basic_auth=f'{JIRA_USER}@{DOMAIN}:{JIRA_TOKEN}')
    headers.update({'content-type': 'application/json'})
    data = {
        'fields': {
            'project': {
                'key': SD
            },
            'summary': task_summary,
            'description': ticket_description,
            'issuetype': {
                'name': issue_type
            },
            'priority': {
                'id': '3'
            }
        }
    }
    try:
        jira_response = http.request(
            method='POST',
            url=search_api,
            body=json.dumps(data),
            headers=headers,
        )
        ticket_id = json.loads(jira_response.data.decode('utf-8'))
        print(ticket_id['key'])
        print('Ticket creation responce (201 means OK):')
        return ticket_id['key']
    except urllib3.exceptions.NewConnectionError:
        print('Connection failed.')


def update_jira_ticket(ticket_id, message):
    """
            Summary: Updates jira ticket function

            Parameters:
                :param ticket_id: str - ticket id, where the function would add
                 a comment
                :param message: str - comment that will be added
        """
    jira_api = JIRA_URL + f'/rest/api/latest/issue/{ticket_id}'
    data = {
        "update": {
            "comment": [{
                "add": {
                    "body":
                    message,
                    "properties": [
                        {
                            "key": "sd.public.comment",
                            "value": {
                                "internal": True
                            }
                        },
                    ]
                }
            }]
        }
    }

    http = urllib3.PoolManager()
    headers = urllib3.util.make_headers(
        basic_auth=f'{JIRA_USER}@{DOMAIN}:{JIRA_TOKEN}')
    headers.update({'content-type': 'application/json'})
    jira_comment_response = http.request(method='PUT',
                                         url=jira_api,
                                         body=json.dumps(data),
                                         headers=headers)
    print(f'HTTP response from the Jira Put'
          f' request:{jira_comment_response.status}')

    return jira_comment_response

