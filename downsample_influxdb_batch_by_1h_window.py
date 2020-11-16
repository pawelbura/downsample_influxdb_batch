"""
downsample_influxdb_batch_by_1h_window.py
    trochę bardziej rozbudowany, wolniejszy ale na pewno się wykona
        (nie skończy się pamięć, bo wykonuje wiele małych zapytań)
    wada: wybiera po jednym wierszu z godziny, więc bez informacji min i max
        potencjalnie tracimy informacje o jakiś spikes
    iteruje po measurements albo po series
    zaleta: dzięki nie używaniu group by, przepisuje dokładnie wszystko
    działanie
        pętla po measurments
            pętla po series
                pętla po 1h oknach czasowych
                    select * into rp_target limi 1
                    czyli wybiera 1. wiersz z każdej godziny
        zapisuje wynik do pliku: {now()}_downsample_influx_batch.csv
        gdzie można zobaczyć ile się zapisało i w jakim czasie
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
influxdb_address = 'localhost'
influxdb_port = 8086
influxdb_user = ''
influxdb_password = ''
protocol = 'line'

db_name = 'telegraf'

# configuration from and where to copy downsampled data
rp_from = 'autogen'
rp_target_selected = 'wybrane'
iterate_through = 'series'

if iterate_through not in ('measurements','series'): raise Exception(
    f"Config error: iterate_through should be in 'measurements','series', got '{iterate_through}''.")
    
# open connection
client = DataFrameClient(influxdb_address, influxdb_port, influxdb_user, influxdb_password, db_name)
# test connection
rs = client.query("show measurements")
print(rs)

# usunięcie retention policy wybrane (opcjonalnie)
# rs = client.query(f"drop retention policy {rp_target_selected} on {db_name}")
# print(rs)

# utworzenie retention policy do którego będzie zapisywany downsampling
rs_rp = client.query(f"create retention policy {rp_target_selected} on {db_name} duration 0s replication 1")
print(rs_rp)

def iterate_series(where_clause):
    #użycie zmiennych globalnych
    global df
    
    # pobranie min i max time z measurement (ustawiam precyzję na nanosekundy, żeby na pewno był cały zakres)
    rs = client.query(f"select * from \"{db_name}\".\"{rp_from}\".\"{measurement}\" \
        where time >= {start_time} and time <= {end_time} {where_clause} order by asc  limit 1")    
    min_time = rs[measurement].index[0].timestamp()*1000000000
    min_time = "{:.0f}".format(min_time)
    rs = client.query(f"select * from \"{db_name}\".\"{rp_from}\".\"{measurement}\" \
        where time >= {start_time} and time <= {end_time} {where_clause} order by desc limit 1")    
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
        rsinsert = client.query(f"select * \
            into \"{db_name}\".\"{rp_target_selected}\".\"{measurement}\" \
            from \"{db_name}\".\"{rp_from}\".\"{measurement}\"  \
            where time >= {min_time}+{i}h and time < {min_time}+{i+1}h and time <= {max_time} \
            and time >= {start_time} and time <= {end_time} \
            {where_clause} order by asc  limit 1")
        #print(rsinsert)
        # zapisanie wyniku do DataFrame
        df = df.append(pd.Series(data=[rsinsert['result']['written'][0], datetime.now()],index=['written','time'], name=measurement))
        #print('.', end='')
        print('.' * rsinsert['result']['written'][0], end='')
    print(datetime.now())

    
# pętla po measurements 
#     pętla okresem downsample_time
#     i insert last() z tego okresu do retention policy target

df = pd.DataFrame()

results = client.query("show measurements")
print(results)

# ustawienie end_time na dziś północ, będzie ten sam moment w czasie dla wszystkich danych przepisanych do rp_wybrane
end_time = datetime.combine(date.today(), time(0, 0))

# ustawienie start_time na now()-14d
start_time = end_time - timedelta(days=14)

print(f"downsampling data from {start_time} to {end_time}")

# formatowanie do timestap influx
end_time = "{:.0f}".format(end_time.timestamp()*1000000000)
start_time = end_time - timedelta(days=14)


for i in results.get_points():
    #print(i)
    #print(f"{type(i)}, {len(i)}")
    print(f"{i['name']}-----")
    measurement = i['name']
    
    # jeżeli conifg iterowanie po seriach
    if iterate_through == 'series':
        # iterowanie po seriach w measurement
        series = client.query(f"show series from \"{db_name}\".\"{rp_from}\".\"{measurement}\" \
            where time >= {start_time} and time <= {end_time} ")          
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
            print('|', end='')
            iterate_series(where_clause)

        if where_clause == '':
            # jeżeli powyższa pętla się nie wykonała, to jescze raz select into bez where
            print('|', end='')
            iterate_series(where_clause)
    elif iterate_through == 'measurements':
        # jeżeli nie po seriach a po measurements, to iterujemy po seriach bez where_clause, wtedy jeden select per measurement
        iterate_series('')
                  
print(f"written count: {df.written.count()}")
print(f"written sum  : {int(df.written.sum())}")
print(f"time  start: {df.time.min()}")
print(f"time    end: {df.time.max()}")
print(f"passed in: {df.time.max()-df.time.min()}")
          
file_name = f"{datetime.now()}_downsample_influx_batch.csv"
df.to_csv(file_name)     
print(f"Skończone. df zapisany do pliku {file_name}")
