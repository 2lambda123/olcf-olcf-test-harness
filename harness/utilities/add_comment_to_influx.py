#!/usr/bin/env python3

################################################################################
# Author: Nick Hagerty
# Date modified: 08-23-2022
################################################################################
# Purpose:
#   Allows users to add comments to a specific event (ie, build_start) of
#   harness jobs in InfluxDB. Logs event back to influx with same timestamp.
################################################################################
# Requirements:
#   Requires a file named harness_keys.py which contains the post_influx_uri,
#   get_influx_uri, influx_token for the targeted InfluxDB instance.
################################################################################

import os
import sys
import requests
import subprocess
import urllib.parse
from datetime import datetime
import argparse

try:
    from status_file import StatusFile
except:
    raise ImportError('Could not import status_file.py. Please make sure the olcf_harness module is loaded.')



# Initialize argparse ##########################################################
parser = argparse.ArgumentParser(description="Updates harness run in InfluxDB with a comment")
parser.add_argument('--jobid', '-j', nargs=1, action='store', required=True, help="Specifies the harness jobID to update jobs for.")
parser.add_argument('--message', '-m', nargs=1, action='store', required=True, help="Comment to add to the record.")
parser.add_argument('--event', nargs=1, action='store', choices=['logging_start', 'build_start', 'build_end', 'submit_start', \
                        'submit_end', 'job_queued', 'binary_execute_start', 'binary_execute_end', 'check_start', 'check_end'], \
                        help="Specifies the harness event to add the comment to.")
################################################################################

# Global URIs and Tokens #######################################################
from harness_keys import post_influx_uri, get_influx_uri, influx_token
################################################################################

# Parse command-line arguments #################################################
args = parser.parse_args()  # event field already validated by 'choices'

# SELECT query - gets other tag information to re-post #########################
tags = StatusFile.INFLUX_TAGS
# These are some commonly needed fields, so we're going to gather these to re-post them in the new record
fields = StatusFile.INFLUX_FIELDS

tagline = ','.join([f"{fld}::tag" for fld in tags])
fieldline = ','.join([f"{fld}::field" for fld in fields if not (fld == 'event_name' or fld == 'event_value')])

event_selector = "last(event_name::field) AS event_name, event_value::field"
where_cond = f"test_id::field = '{args.jobid[0]}'"
if args.event:
    event_selector = "event_name::field AS event_name, event_value::field"
    where_cond += f" AND event_name::field = '{args.event[0]}'"

query = f"SELECT {tagline}, {fieldline}, {event_selector} FROM events WHERE {where_cond} GROUP BY job_id"
required_entries = ['test', 'app', 'test_id', 'runtag', 'machine', 'event_name', 'event_value']
################################################################################

def check_data(entry):
    # Check if all required columns exist ######################################
    missing_entries = []
    for req in required_entries:
        if not req in entry:
            missing_entries.append(req)
    if len(missing_entries) > 0:
        return [ False, f"Missing entries: {','.join(missing_entries)}" ]
    return [True, '']

def query_influx():
    """
        Send the query to get all running jobs
    """
    headers = {
        'Authorization': "Token " + influx_token,
        'Accept': "application/json"
    }
    url = f"{get_influx_uri}&db=accept&q={urllib.parse.quote(query)}"
    try:
        r = requests.get(url, headers=headers, params={'q': 'requests+language:python'})
    except requests.exceptions.ConnectionError as e:
        print("InfluxDB is not reachable. Request not sent.")
        print(str(e))
        sys.exit(1)
    except Exception as e:
        print(f"Failed to send to {url}:")
        print(str(e))
        sys.exit(2)
    resp = r.json()
    if not 'series' in resp['results'][0]:
        print(f"No Running tests found.\nFull query: {query}.\nFull response: {resp}")
        return []
    # each entry in series is a record
    col_names = resp['results'][0]['series'][0]['columns']
    values = resp['results'][0]['series'][0]['values']
    if not len(values) == 1:
        print(f"Query returned {len(values)} results, expected 1. Exiting.")
        sys.exit(1)
    # Let's do the work of transforming this into a list of dicts
    ret_data = {}
    for c_index in range(0, len(col_names)):
        ret_data[col_names[c_index]] = values[0][c_index]
    should_add, reason = check_data(ret_data)
    if not should_add:
        test_id = data_tmp['test_id'] if 'test_id' in data_tmp else 'unknown'
        print(f"Invalid record associated with test_id {test_id}. Reason: {reason}. Exiting.")
        sys.exit(1)
    return ret_data

def post_update_to_influx(d):
    """ POSTs updated event to Influx """
    headers = {
        'Authorization': "Token " + influx_token,
        'Content-Type': "application/octet-stream",
        'Accept': "application/json"
    }
        #'Content-Type': "text/plain; charset=utf-8",
    log_time = datetime.strptime(d['time'], "%Y-%m-%dT%H:%M:%S.%fZ")
    log_ns = int(datetime.timestamp(log_time) * 1000 * 1000 * 1000)

    tagline = ','.join([f"{fld}={d[fld]}" for fld in tags])
    fieldline = ','.join([f"{fld}=\"{d[fld]}\"" for fld in fields])
    influx_event_record_string = f'events,{tagline} {fieldline} {str(log_ns)}'
    try:
        r = requests.post(post_influx_uri, data=influx_event_record_string, headers=headers)
        if int(r.status_code) < 400:
            print(f"Successfully updated {d['test_id']} with {influx_event_record_string}.")
            return True
        else:
            print(f"Influx returned status code: {r.status_code} in response to data: {influx_event_record_string}")
            print(r.text)
            return False
    except requests.exceptions.ConnectionError as e:
        print(f"InfluxDB is not reachable. Request not sent: {influx_event_record_string}")
        os.chdir(currentdir)
        return False
    except Exception as e:
        # TODO: add more graceful handling of unreachable influx servers
        print(f"Failed to send {influx_event_record_string} to {influx_url}:")
        print(e)
        os.chdir(currentdir)
        return False

data = query_influx()

# set d['timestamp'] to set a timestamp
timestamp = datetime.now().isoformat()
# reason or comment field

if data['comment']:
    print(f"Warning: found an existing comment on this record: {data['comment']}.\nAppending to this comment.")
    data['comment'] += f"\n{timestamp} - {os.environ['USER']}: {args.message[0]}"
else:
    data['comment'] = f"{timestamp} - {os.environ['USER']}: {args.message[0]}."

post_update_to_influx(data)

sys.exit(0)