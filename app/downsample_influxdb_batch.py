#!/usr/bin/env python
# coding: utf-8

# In[ ]:


"""influxdb batch downsampling


downsample_influxdb_batch.py


3 modes:
- simple_group_by_fullscan
- iterate_by_1h_window_measurements_only
- iterate_by_1h_window_series

configuration in workdir/config.ini

see README.md

"""

import pandas as pd
from influxdb import DataFrameClient
from datetime import datetime, timedelta, date, time
import re
from configparser import ConfigParser

# requirements:
## python3 (f-strings)
### pip3 install pandas
### pip3 install influxdb

#Read config.ini file
config_object = ConfigParser()
config_object.read('workdir/config.ini')

# configuration for connection
influxdb_address = config_object.get('influxdb_connection','influxdb_address', 
                                     fallback='localhost')
influxdb_port = config_object.get('influxdb_connection','influxdb_port', fallback='8086')
influxdb_user = config_object.get('influxdb_connection','influxdb_user', fallback='')
influxdb_password = config_object.get('influxdb_connection','influxdb_password', 
                                      fallback='')

#database name
db_name = config_object.get('influxdb_db','db_name', fallback='')

# configuration from and where to copy downsampled data
rp_from = config_object.get('influxdb_db','retention_policy_from', fallback='autogen')
rp_target = config_object.get('influxdb_db','retention_policy_to', 
                              fallback='downsampled')

# downsample_mode configuration
downsample_mode = config_object.get('downsample_mode','mode', 
                                    fallback='simple_group_by_fullscan')

# retention policy drop before 
# designed to be used for testing purposes
# WARNING! use it carefully, it deletes all data in retention policy with name retention_policy_to. ALL THE DATA. 
# DEFAULT = NO
rp_target_drop_before = config_object.get('downsample_mode','retention_policy_to_drop_before_downsampling', 
                              fallback='NO')
rp_target_drop_before_YES = 'yes_and_I_know_it_is_dengerous_and_drops_data'


# TODO: dodać to do parametrów z konfiguracji i stosować w każdej z metod
# bo na razie uwżywane tylko w simple group by 
downsample_time = '1d'

# df zapisuję wyniki pośrednie, żeby na koniec podsumować
# TODO: pandas dataframe użyty dla ułatwienia, w zasadzie niepotrzebny, a przez pandas 
# trzeba użyć specjalnego obrazu dockera, zamiast najprostrzego python slim, bo nie działa na rasperry pi
# więc zamiast użyć coś prostego jak list of sets, czy coś takiego
df = pd.DataFrame()

# open connection
client = DataFrameClient(influxdb_address, influxdb_port, influxdb_user, influxdb_password, db_name)
# test connection
rs = client.query("show measurements")
print(rs)

# check if rp_from exists
rs = client.query("show retention policies on telegraf")
if not True in [True if x['name']==rp_from else False for x in rs.get_points()]:
    raise Exception(f"Configuration error: retention policy '{rp_from}' not found on '{db_name}' db. "
                    "Verify your config.")

print(f"{datetime.now()}| START |mode:{downsample_mode}|")
print(f"{datetime.now()}|Retention policy source: {rp_from}|Retention policy target: {rp_target}|")

# odczytanie z konfiguracji zasięgu 
start_date_days_ago = config_object.getint('downsample_mode','start_date_days_ago', fallback=7)
end_date_days_ago   = config_object.getint('downsample_mode','end_date_days_ago', fallback=0)

from datetime import datetime, timedelta, date, time
# ustawienie end_time na dziś północ, będzie ten sam moment w czasie dla wszystkich danych przepisanych do rp_wybrane
end_time = datetime.combine(date.today(), time(0, 0)) - timedelta(days=end_date_days_ago)

# ustawienie start_time na now()-14d
start_time = datetime.combine(date.today(), time(0, 0)) - timedelta(days=start_date_days_ago)

print(f"{datetime.now()}|downsampling data from {start_time} to {end_time}")

# formatowanie do timestap influx
end_time = "{:.0f}".format(end_time.timestamp()*1000000000)
start_time = "{:.0f}".format(start_time.timestamp()*1000000000)

    
# modes
if downsample_mode == 'simple_group_by_fullscan' :

    """
    downsample_influxdb_batch_simple_group_by_fullscan
    """
    # [opcjonalnie] usunięcie retention policy dzinne
    # celowo wstawione dopiero po ustaleniu trybu (a więc powtórzone)
    if rp_target_drop_before == rp_target_drop_before_YES:
        print("WARNING!!! Configuration set to drop target retention policy AND ALL DATA inside! Data may be lost.")
        rs = client.query(f"drop retention policy {rp_target} on {db_name}")
        print(rs)

    # utworzenie retention policy do którego będzie zapisywany downsampling
    rs = client.query(f"create retention policy {rp_target} on {db_name} duration 0s replication 1")
    print(rs)

    # pętla po measurements
    # i insert mean do retention policy dzienne

    ## uwaga! niestety mean() bierze pod uwagę tylko wartośli liczbowe, żeby nie tracić wartości tagów trzeba dać group by * dać
    ## uwaga! mean(), min(), max() zmieniają nazwy, dlatego iteruję po field keys i ustawiam nazwy bez zmian 

    results = client.query("show measurements")
    print(results)
    print(f"{datetime.now()}|start:{datetime.now()}")
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
        rsinsert = client.query(f"select {field_names}, min(*), max(*) \ 
                                into \"{db_name}\".\"{rp_target}\".\"{measurement}\"                                 from \"{db_name}\".\"{rp_from}\".\"{measurement}\"                                 where time >= {start_time} and time <= {end_time}                                 group by *, time({downsample_time})")
        print(rsinsert)
        # zapisanie wyniku do DataFrame
        df = df.append(pd.Series(data=[rsinsert['result']['written'][0], datetime.now()],index=['written','time'], name=measurement))

    print(f"{datetime.now()}|stop:{datetime.now()}")

elif downsample_mode in ('iterate_by_1h_window_series', 'iterate_by_1h_window_measurements_only')  :
    """
    downsample_influxdb_batch_by_1h_window
        2 modes:
            iterate_by_1h_window_series
            iterate_by_1h_window_measurements_only
    """

    # ustalenie czy iterujemy po mesurements i series
    if downsample_mode == 'iterate_by_1h_window_series':
        iterate_through = 'series'
    elif downsample_mode == 'iterate_by_1h_window_measurements_only':
        iterate_through = 'measurements'
    if iterate_through not in ('measurements','series'): 
        raise Exception(f"Config error: iterate_through should be in 'measurements','series', got '{iterate_through}''.")

              
    # [opcjonalnie] usunięcie retention policy dzinne 
    # celowo wstawione dopiero po ustaleniu trybu (a więc powtórzone)
    if rp_target_drop_before == rp_target_drop_before_YES:
        print("WARNING!!! Configuration set to drop target retention policy AND ALL DATA inside! Data may be lost.")
        rs = client.query(f"drop retention policy {rp_target} on {db_name}")
        print(rs)

    # utworzenie retention policy do którego będzie zapisywany downsampling
    rs_rp = client.query(f"create retention policy {rp_target} on {db_name} duration 0s replication 1")
    print(rs_rp)

    def iterate_series(where_clause):
        # funkcja bazuje na zmiennych globalnych, całej konfituracji ale też aktualnym measurement do odczytu
        # do zapisu tylko df:
        global df

        # pobranie min i max time z measurement (ustawiam precyzję na nanosekundy, żeby na pewno był cały zakres)
        rs = client.query(f"select * from \"{db_name}\".\"{rp_from}\".\"{measurement}\"             where time >= {start_time} and time <= {end_time} {where_clause} order by asc  limit 1")    
        # może nie zwrócić nic, bo ograniczone czasem, wtedy po prostu skip
        if rs == {}:
            return

        min_time = rs[measurement].index[0].timestamp()*1000000000
        min_time = "{:.0f}".format(min_time)
        rs = client.query(f"select * from \"{db_name}\".\"{rp_from}\".\"{measurement}\"             where time >= {start_time} and time <= {end_time} {where_clause} order by desc limit 1")    
        max_time = rs[measurement].index[0].timestamp()*1000000000
        max_time = "{:.0f}".format(max_time)

        # ile godzin od min do max time (użyte do pętli)
        hours = round((int(max_time)-int(min_time))/1000000000/60/60)
        print(f"from {min_time} to {max_time} ~= {hours}h")

        #pętla po godzinnych przedziałach (+1 na wypadek zaokrągleń)
        for i in range(hours+1):
            # wybieram pierwszy wiersz, sortowanie rosnące, w każdym oknie przesuwnym o 1h od min_time do max_time ale zawsze nie później niż end_time  
            # możnaby też zrobić ostatni wiersz (czyli dokładniej pierwszy z sortowaniem malejącym)
            # TODO: zrobić test porównania obu powyższych czy są różnice wydajnościowe
            rsinsert = client.query(f"select *                 into \"{db_name}\".\"{rp_target}\".\"{measurement}\"                 from \"{db_name}\".\"{rp_from}\".\"{measurement}\"                  where time >= {min_time}+{i}h and time < {min_time}+{i+1}h and time <= {max_time}                 and time >= {start_time} and time <= {end_time}                 {where_clause} order by asc  limit 1")
            #print(rsinsert)
            # zapisanie wyniku do DataFrame
            df = df.append(pd.Series(data=[rsinsert['result']['written'][0], datetime.now()],index=['written','time'], name=measurement))
            #print('.', end='')
            print('.' * rsinsert['result']['written'][0], end='')
        print(datetime.now())


    # pętla po measurements 
    #     pętla okresem downsample_time
    #     i insert last() z tego okresu do retention policy target

    # pobranie measurements
    results = client.query(f"show measurements on \"{db_name}\" ")
    print(results)

    for i in results.get_points():
        #print(i)
        #print(f"{type(i)}, {len(i)}")
        print(f"{i['name']}-----")
        measurement = i['name']

        # jeżeli conifg iterowanie po seriach
        if iterate_through == 'series':
            # iterowanie po seriach w measurement
            series = client.query(f"show series from \"{db_name}\".\"{rp_from}\".\"{measurement}\"                 where time >= {start_time} and time <= {end_time} ")          
            where_clause = ''
            for s in series.get_points():
                print(f"series:{s['key']}")
                # jeżeli nie ma przecinka to następny
                if ',' not in s['key']:
                    continue
                # jeżeli jest przecinek to wstawiamy where
                where_clause = ' and '
                # to wycinamy "measurement," i dodajemy cudzysłowia na początek
                where_clause += "\""+s['key'][len(measurement)+1:]
                #zastępujemy ',' przez ' AND ' i dodajemy cudzysłowia
                where_clause = re.sub(r"(?<!\\),", "' and \"", where_clause)
                where_clause = re.sub(r"(?<!\\)=", "\"='", where_clause)
                #cudzysłow na koniec
                where_clause += "'"
                # usuwamy "\" (dodawane jako escape char spacji, przecinka, =)
                where_clause = where_clause.replace("\\","")
                # i wykonujemy pętle po przedziałach godzinowych  
                #print(f"where:{where_clause}")
                print(':', end='')
                iterate_series(where_clause)

            if where_clause == '':
                # jeżeli powyższa pętla się nie wykonała, to jescze raz select into bez where
                print(':', end='')
                iterate_series(where_clause)
        elif iterate_through == 'measurements':
            # jeżeli nie po seriach a po measurements, to iterujemy po seriach bez where_clause, wtedy jeden select per measurement
            iterate_series('')

else:
    raise Exception(f"Config error: mode should be in 'simple_group_by_fullscan', "
                    "'iterate_by_1h_window_series', 'iterate_by_1h_window_measurements_only', "
                    "got '{downsample_mode}''.")

print(f"{datetime.now()}|written count: {df.written.count()}")      # how many select...into done
print(f"{datetime.now()}|written sum  : {int(df.written.sum())}")   # how many datapoints written
print(f"{datetime.now()}|time  start: {df.time.min()}")             # first select done
print(f"{datetime.now()}|time    end: {df.time.max()}")             # last select done
print(f"{datetime.now()}|passed in: {df.time.max()-df.time.min()}")

file_name = f"workdir/{datetime.now()}_downsample_influx_batch_{downsample_mode}.csv"
df.to_csv(file_name)     
print(f"{datetime.now()}|Finished. Result written to file: {file_name}")
print(f"{datetime.now()}| STOP |mode:{downsample_mode}|")
print(f"{datetime.now()}|_____________________________|")

