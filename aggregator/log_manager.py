# Python interface for managing aggregated logs

import sqlite3
import time
import os

class LogManager:

  def __init__(self, start_time = 0, end_time = int(time.time())):

    # timestamps for start/end point for logs to retrieve
    self.start_time = int(start_time)
    self.end_time = int(end_time)

    db_file = os.path.join(os.path.dirname(__file__), 'aggregated_logs.db')
    self.conn = sqlite3.connect(db_file)
    sql_file = os.path.join(os.path.dirname(__file__), 'aggregator.sql')
    with open(sql_file, 'rb') as initialization_file:
      self.conn.executescript(initialization_file.read())
    self.cursor = self.conn.cursor()

  # Adds log entry into database
  #
  # params:
  #   log_entry: tab-separated column values for log
  def add_log_entry(self, log_entry):
    log_columns = log_entry.split("\t")
    if len(log_columns) == 8:
      for i, col in enumerate(log_columns):
        if col == 'null':
          log_columns[i] = None
      self.cursor.execute('INSERT OR REPLACE INTO Log VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                          (log_columns[0], log_columns[1], log_columns[2], log_columns[3],
                           log_columns[4], log_columns[5], log_columns[6], log_columns[7]))
      self.conn.commit()

  # Adds multiple log entries into database
  #
  # params:
  #   log_entries: tab-separated column values for log, one per line
  def add_log_entries(self, log_entries):
    log_entry_lines = log_entries.split("\n")
    for log_entry in log_entry_lines:
      self.add_log_entry(log_entry)

  # Retrieve last timestamp on database
  #
  def last_timestamp(self, destination_entity):
    self.cursor.execute('SELECT timestamp FROM Log WHERE destination_entity = ? ORDER BY timestamp DESC LIMIT 1', (destination_entity,))
    result = self.cursor.fetchone()
    if result is None:
      return None
    return result[0]

  # Retrieve successful log read entries in a specified time period
  def get_reads(self, start_timestamp = None, end_timestamp = None):
    if start_timestamp is None:
      start_timestamp = self.start_time if self.start_time is not None else 0
    if end_timestamp is None:
      end_timestamp = self.end_time if self.end_time is not None else int(time.time())
    self.cursor.execute('SELECT * FROM Log WHERE request_type = \'READ\' AND status = 200 AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC', (start_timestamp, end_timestamp))
    return self.cursor.fetchall()

  # Retrieve successful log on file movement in a specified time period
  def get_movings(self, start_timestamp = None, end_timestamp = None):
    if start_timestamp == None:
      start_timestamp = self.start_time if self.start_time is not None else 0
    if end_timestamp == None:
      end_timestamp = self.end_time if self.end_time is not None else int(time.time())
    self.cursor.execute('SELECT * FROM Log WHERE (request_type = \'TRANSFER\' OR request_type = \'REPLICATE\' OR request_type = \'DISTRIBUTED_REPLICATE\') AND status = 200 AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC', (start_timestamp, end_timestamp))
    return self.cursor.fetchall()

  # Retrive log on redirect (read with 302) in a specified time period
  def get_redirects(self, start_timestamp = None, end_timestamp = None):
    if start_timestamp is None:
      start_timestamp = self.start_time if self.start_time is not None else 0
    if end_timestamp is None:
      end_timestamp = self.end_time if self.end_time is not None else int(time.time())
    self.cursor.execute('SELECT * FROM Log WHERE request_type = \'READ\' AND status = 302 AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC', (start_timestamp, end_timestamp))
    return self.cursor.fetchall()

  # Retrieve successful log read entries, grouped by source_entity
  def get_reads_grouped_by_source(self, uuid):
    self.cursor.execute('SELECT source_entity, COUNT(source_entity) AS weight FROM Log '
      'WHERE uuid = ? AND request_type = "READ" AND status = 200 AND timestamp >= ? AND timestamp <= ? GROUP BY source_entity', (uuid, self.start_time, self.end_time))
    return self.cursor.fetchall()

  # Retrieve all distinct destination entities.
  def get_unique_destinations(self):
    self.cursor.execute('SELECT DISTINCT destination_entity FROM Log WHERE request_type = "READ" AND timestamp >= ? AND timestamp <= ?', (self.start_time, self.end_time))
    server_tuples = self.cursor.fetchall()

    servers = []
    for server_tuple in server_tuples:
      servers.append(server_tuple[0])
    return servers

  # Returns a count for unique uuids a uuid is interdependent with, and how many requests for each interdependent request are made
  def get_interdependency_grouped_by_uuid(self, uuid):
    self.cursor.execute(
      "SELECT uuid, SUM(count) FROM (SELECT source_uuid AS uuid, COUNT(*) AS count FROM Log "
      "WHERE uuid = ? AND source_uuid IS NOT null AND timestamp >= ? AND timestamp <= ? "
      "GROUP BY source_uuid "
      "UNION ALL SELECT uuid, COUNT(*) AS count FROM Log "
      "WHERE source_uuid = ? AND timestamp >= ? AND timestamp <= ? GROUP BY uuid) "
      "GROUP BY uuid", (uuid, self.start_time, self.end_time, uuid, self.start_time, self.end_time))
    return self.cursor.fetchall()

  # Retrieve all distinct uuids.
  #
  # params:
  #   start_timestamp: returned logs start from this integer timestamp
  #   end_timestamp: returned logs end by this integer timestamp
  def get_unique_uuids(self):
    self.cursor.execute('SELECT DISTINCT uuid FROM Log WHERE timestamp >= ? AND timestamp <= ? AND status = 200', (self.start_time, self.end_time))
    uuid_tuples = self.cursor.fetchall()

    uuids = []
    for uuid_tuple in uuid_tuples:
      uuids.append(uuid_tuple[0])
    return uuids

  # Retrieve number of successful read counts for a specific uuid.
  #
  # params:
  #   start_timestamp: returned logs start from this integer timestamp
  #   end_timestamp: returned logs end by this integer timestamp
  def successful_read_count(self, uuid):
    self.cursor.execute('SELECT count(*) FROM Log WHERE request_type = "READ" AND status = 200 AND uuid = ? AND timestamp >= ? AND timestamp <= ?', (uuid, self.start_time, self.end_time))
    request_count_result = self.cursor.fetchone()
    if request_count_result is None:
      raise Exception('Number of requests could not be found for uuid: ' + uuid)

    return request_count_result[0]

  # Closes the connection to the database
  def __del__(self):
    self.conn.close()
