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

"""Processes standard read / write yaml block for dynamic loading of data.

The goal is to create standard re-usable input output blocks.  These functions
are extensible, and should include additional sources and destinations over
time.
Key benfits include:

  - Allows single point API revision for common read / write tasks.
  - Reduce risk with test case coverage for this module inherited by recipes
  using it.
  - Using standard blocks is a big time savings.

"""

from bqflow.util.storage_api import parse_path, makedirs_safe, object_put, bucket_create
from bqflow.util.bigquery_api import BigQuery, query_parameters
from bqflow.util.sheets_api import Sheets 
from bqflow.util.csv import rows_to_csv, rows_to_type


def get_rows(config, auth, source, as_object=False, unnest=False):
  """Processes standard read yaml block for dynamic loading of data.

  Allows us to quickly pull a column or columns of data from and use it as an
  input
  into a script. For example pull a list of ids from bigquery and act on each
  one.

  - When pulling a single column specify unnest = True. Returns list AKA
  values.
  - When pulling a multiple columns specify unnest = False. Returns list of
  lists AKA rows.
  - Values are always given as a list ( unnest will trigger necessary wrapping ).
  - Values, bigquery, sheet are optional, if multiple given result is one
  continous iterator.
  - Extensible, add a handler to define a new source ( be kind update the
  documentation yaml ).

  Include the following yaml in a recipe, then in the run.py handler when
  encountering that block pass it to this function and use the returned results.

    from bqflow.util.data import get_rows

    var_yaml = {
      "in":{
        "unnest":[ boolean ],
        "values": [ integer list ],
        "bigquery":{
          "auth":"[ user or service ]",
          "dataset": [ string ],
          "query": [ string ],
          "legacy":[ boolean ]
        },
        "bigquery":{
          "auth":"[ user or service ]",
          "dataset": [ string ],
          "table": [ string ],
        },
        "sheets":{
          "auth":"[ user or service ]",
          "sheet":[ string - full URL, suggest using share link ],
          "tab":[ string ],
          "range":[ string - A1:A notation ]
        }
      }
    }

    values = get_rows('user', var_yaml)

  Args:
    config: (yaml) The authentication details.
    auth: (string) The type of authentication to use, user or service.
    source: (yaml) A yaml block resembling var_yaml described above.

  Returns:
    If unnest is False: Returns a list of row values [[v1], [v2], ... ]
    If unnest is True: Returns a list of values [v1, v2, ...]
"""

  # if handler points to list, concatenate all the values from various sources into one list
  if isinstance(source, list):
    for s in source:
      for r in get_rows(config, auth, s):
        yield r

  # if handler is an endpoint, fetch data
  else:
    if 'values' in source:
      if isinstance(source['values'], list):
        for value in source['values']:
          yield value
      else:
        yield source['values']

    # should be sheets, deprecate sheet over next few releases
    if 'sheet' in source:
      rows = Sheets(config, source['sheet'].get('auth', auth)).sheet_read(
        source['sheet']['sheet'],
        source['sheet']['tab'],
        source['sheet']['range'],
      )

      for row in rows:
        yield row[0] if unnest or source.get('single_cell', False) or source.get('unnest', False) else row

    if 'sheets' in source:
      rows = Sheets(config, source['sheets'].get('auth', auth)).sheet_read(
        source['sheets']['sheet'],
        source['sheets']['tab'],
        source['sheets']['range'],
      )

      if rows:
        for row in rows:
          yield row[0] if unnest or source.get('single_cell', False) or source.get('unnest', False) else row
      else:
        print("No rows in source.")

    if 'bigquery' in source:

      rows = []
      as_object = as_object or source['bigquery'].get('as_object', False)
      unnest = unnest or source.get('single_cell', False) or source.get('unnest', False)

      if 'table' in source['bigquery']:
        rows = BigQuery(config, source['bigquery'].get('auth', auth)).table_to_rows(
          source['bigquery'].get('project', config.project),
          source['bigquery']['dataset'],
          source['bigquery']['table'],
          as_object=as_object or source['bigquery'].get('as_object', False)
        )

      else:
        rows = BigQuery(config, source['bigquery'].get('auth', auth)).query_to_rows(
          source['bigquery'].get('project', config.project),
          source['bigquery']['dataset'],
          query_parameters(source['bigquery']['query'], source['bigquery'].get('parameters', {})),
          legacy=source['bigquery'].get('legacy', False),
          as_object=as_object or source['bigquery'].get('as_object', False)
        )

      for row in rows:
        yield row[0] if not as_object and unnest else row


def put_rows(config, auth, destination, rows):
  """Processes standard write yaml block for dynamic export of data.

  Allows us to quickly write the results of a script to a destination.  For
  example
  write the results of a DCM report into BigQuery.

  - Will write to multiple destinations if specified.
  - Extensible, add a handler to define a new destination ( be kind update the
  documentation yaml ).

  Include the following yaml in a recipe, then in the run.py handler when
  encountering that block pass it to this function and use the returned results.

    from bqflow.util.data import put_rows

    var_yaml = {
      "out":{
        "bigquery":{
          "auth":"[ user or service ]",
          "dataset": [ string ],
          "table": [ string ]
          "schema": [ yaml - standard bigquery schema yaml ],
          "header": [ boolean - true if header exists in rows ]
          "disposition": [ string - same as BigQuery documentation ]
          "merge": [ string list - columns to maintain uniqueness on ]
        },
        "sheets":{
          "auth":"[ user or service ]",
          "sheet":[ string - full URL, suggest using share link ],
          "tab":[ string ],
          "range":[ string - A1:A notation ]
          "append": [ boolean - if sheet range should be appended to ]
          "delete": [ boolean - if sheet range should be cleared before writing ]
          ]
        },
        "storage":{
          "auth":"[ user or service ]",
          "bucket": [ string ],
          "path": [ string ]
        },
        "file":[ string - full path to place to write file ],
      }
    }

    values = put_rows('user', var_yaml)

  Args:
    auth: (string) The type of authentication to use, user or service.
    rows: ( iterator ) The list of rows to be written, if NULL no action is performed.
    schema: (yaml) A bigquery schema definition.
    destination: (yaml) A yaml block resembling var_yaml described above. rows (
      list ) The data being written as a list object. 

  Returns:
    If unnest is False: Returns a list of row values [[v1], [v2], ... ]
    If unnest is True: Returns a list of values [v1, v2, ...]
"""

  if rows is None:
    if config.verbose:
      print('PUT ROWS: Rows is None, ignoring write.')
    return

  if 'bigquery' in destination:

    table = destination['bigquery']['table']
    if 'merge' in destination['bigquery']:
      table += '_MERGE'

    BigQuery(config, destination['bigquery'].get('auth', auth)).rows_to_table(
      project_id = destination['bigquery'].get('project_id', config.project),
      dataset_id = destination['bigquery']['dataset'],
      table_id = table,
      rows = rows,
      source_format=destination['bigquery'].get('format', 'CSV') ,
      schema = destination['bigquery'].get('schema'),
      disposition = destination['bigquery'].get('disposition', 'WRITE_TRUNCATE'),
      header=destination['bigquery'].get('header', False)
    )

    if 'merge' in destination['bigquery']:
      BigQuery(config, destination['bigquery'].get('auth', auth)).table_merge(
        project_id = destination['bigquery'].get('project_id', config.project),
        dataset_id = destination['bigquery']['dataset'],
        source_table_id = table,
        destination_table_id = destination['bigquery']['table'],
        columns=destination['bigquery']['merge']
      )

  elif 'sheets' in destination:
    if destination['sheets'].get('delete', False):
      Sheets(config, source['sheets'].get('auth', auth)).tab_clear(
        destination['sheets']['sheet'],
        destination['sheets']['tab'],
        destination['sheets']['range'],
      )

    Sheets(config, source['sheets'].get('auth', auth)).tab_write(
      destination['sheets']['sheet'],
      destination['sheets']['tab'],
      destination['sheets']['range'],
      rows_to_type(rows),
      destination['sheets'].get('append', False),
    )

  elif 'file' in destination:
    with open(destination['file'], 'w') as file:
      file.write(rows_to_csv(rows).read())

  elif 'storage' in destination and destination['storage'].get(
      'bucket') and destination['storage'].get('path'):
    bucket_create(
      config,
      destination['storage'].get('auth', auth),
      config.project,
      destination['storage']['bucket']
    )

    # put the file
    file_out = destination['storage']['bucket'] + ':' + destination['storage']['path'] 
    if config.verbose:
      print('SAVING', file_out)
    object_put(config, auth, file_out, rows_to_csv(rows))

  else:
    return rows
