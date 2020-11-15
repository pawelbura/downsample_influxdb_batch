"""
downsample_influxdb_batch_simple_group_by_fullscan.py

    prosty, o ile fullscan się wykona w skończonym czasie
    wada: oparty o group by *, więc może gubić część danych
        w fields, które nie sa tagami i nie dają rozsądnego wyniku średniego
            (strings i boolean, ale też np identyfikatory numeryczne)
    działanie:
        pętla po measurements
            dla każdego robi select mean(*) into rp_target group by *
            z zachowaniem nazw fields 
            i dodaje min(*) i max(*)
"""
import pandas as pd
from influxdb import DataFrameClient
from datetime import datetime, timedelta, date, time
import re

# requirements:
## python3 (f-strings)
### pip3 install pandas
### pip3 install influxdb

# configuration for connection
influxdb_address = '192.168.1.128'
influxdb_port = 8086
influxdb_user = ''
influxdb_password = ''
protocol = 'line'

db_name = 'telegraf'

# configuration from and where to copy downsampled data
rp_from = 'autogen'
rp_target = 'dzienne'
downsample_time = '1d'

# open connection
client = DataFrameClient(influxdb_address, influxdb_port, influxdb_user, influxdb_password, db_name)
# test connection
rs = client.query("show measurements")
print(rs)

# [opcjonalnie] usunięcie retention policy dzinne 
# rs = client.query(f"drop retention policy {rp_target} on {db_name}")
# print(rs)

# utworzenie retention policy do którego będzie zapisywany downsampling
rs = client.query(f"create retention policy {rp_target} on {db_name} duration 0s replication 1")
print(rs)

# pętla po measurements
# i insert mean do retention policy dzienne

## uwaga! niestety mean() bierze pod uwagę tylko wartośli liczbowe, żeby nie tracić wartości tagów trzeba dać group by * dać
## uwaga! mean(), min(), max() zmieniają nazwy, dlatego iteruję po field keys i ustawiam nazwy bez zmian 

results = client.query("show measurements")
print(results)
print(f"start:{datetime.now()}")
for i in results.get_points():
    #print(i)
    #print(f"{type(i)}, {len(i)}")
    print(f"{i['name']}...............................................")
    measurement = i['name']
    field_names = ''
    rs = client.query(f"show field keys from {measurement}")
    #print(rs)
    # wymieniam pola (fields), żeby funkcja mean(*) nie zmieniła nazw pól, i dodaję min i max
    for field in rs.get_points():    
          print(f"{measurement}    {field}")
          #print(f"mean({field['fieldKey']}) as {field['fieldKey']},")
          if field['fieldType'] not in ('string','boolean'):
              if len(field_names) > 0: field_names += ', '
              field_names += f"mean(\"{field['fieldKey']}\") as \"{field['fieldKey']}\""
    rsinsert = client.query(f"select {field_names}, min(*), max(*) into \"{db_name}\".\"{rp_target}\".\"{measurement}\" from \"{db_name}\".\"{rp_from}\".\"{measurement}\" group by *, time({downsample_time})")
    print(rsinsert)
print(f"stop:{datetime.now()}")
