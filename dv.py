#!/usr/bin/env python3

###########################################################################
#
#  Copyright 2020 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
###########################################################################

import yaml
import argparse
import textwrap

from bqflow.util.bigquery_api import get_schema
from bqflow.util.csv import rows_to_type, rows_print
from bqflow.util.configuration import Configuration
from bqflow.util.dv_api import report_file, report_to_rows, report_clean
from bqflow.util.google_api import API_DBM

def task_template(auth, report):
  """Helper to create a BQFlow compatible task yaml from DV report."""

  task = {
    "dv_report":{
      "auth":auth,
      "report": {
        "name":report['metadata']['title'],
        "body":report
      },
      "out":{
        "bigquery":{
          "auth":auth,
          "dataset":"DV360_Dataset",
          "table":"DV360_Report",
        }
      }
    }
  }

  try: del task['dv_report']['report']['body']['queryId']
  except KeyError: pass

  return task


def main():

  parser = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      description=textwrap.dedent("""\
      Command line to help debug DV360 reports and build reporting tools.

      Examples:
        To get list of reports: python dv.py --list -u [user credentials path]
        To get report yaml: python dv.py --report [id] -u [user credentials path]
        To get report schema: python dv.py --schema [id] -u [user credentials path]
        To get report sample: python dv.py --sample [id] -u [user credentials path]

  """))

  # create parameters
  parser.add_argument('--user', '-u', help='Path to USER credentials yaml file.', default=None)
  parser.add_argument('--service', '-s', help='Path to SERVICE credentials yaml file.', default=None)

  parser.add_argument('--report', help='report ID to pull yaml definition', default=None)
  parser.add_argument('--schema', help='report ID to pull schema format', default=None)
  parser.add_argument('--sample', help='report ID to pull sample data', default=None)
  parser.add_argument('--list', help='list reports', action='store_true')
  parser.add_argument('--task', help='report ID to pull yaml task', default=None)

  # initialize project
  args = parser.parse_args()
  config = Configuration(
    user=args.user,
    service=args.service
  )

  auth = 'service' if args.service else 'user'

  # get report
  if args.report:
    report = API_DBM(config, auth).queries().get(queryId=args.report).execute()
    print(yaml.dump(report, indent=2, sort_keys=True))

  # get task yaml
  elif args.task:
    report = API_DBM(config, auth).queries().get(queryId=args.task).execute()
    print(yaml.dump(task_template(auth, report), indent=2, sort_keys=True))

  # get schema
  elif args.schema:
    filename, report = report_file(config, auth, args.schema, None, 10)
    rows = report_to_rows(report)
    rows = report_clean(rows)
    rows = rows_to_type(rows)
    print(yaml.dump(get_schema(rows)[1], indent=2, sort_keys=True))

  # get sample
  elif args.sample:
    filename, report = report_file(config, auth, args.sample, None, 10)
    rows = report_to_rows(report)
    rows = report_clean(rows)
    rows = rows_to_type(rows)
    for r in rows_print(rows, row_min=0, row_max=20):
      pass

  # get list
  else:
    for report in API_DBM(config, auth, iterate=True).queries().list().execute():
      print(yaml.dump(report, indent=2, sort_keys=True))


if __name__ == '__main__':
  main()
