# downsample_influxdb_batch
python batch script to downsample influxdb database in a batch mode

### This script is inteded to be small, used from time to time and run in a batch mode.
### Script prepared to run in docker container

### Other ways to look at
There are plenty of ways to do downsampling, for example the one suggested by influx:
 - use influxdb continuous query to insert downsampled data to another retention policy and configure original retention policy to be restricted to shorter time: https://docs.influxdata.com/influxdb/v1.8/guides/downsample_and_retain/ . But this needs to be done upfront.
 - From TICK stack, you can use Kapacitor, sample node, as described here: https://archive.docs.influxdata.com/kapacitor/v1.3/nodes/sample_node/ . But this is another comprehensive tool to configure.

# How to run
Clone/get repository to your target machine, for instance:
```bash
git clone https://github.com/pawelbura/downsample_influxdb_batch.git
cd downsample_influxdb_batch/ 
```

## docker build
to build docker image from code execute:
```bash
docker build . -t downsample_influxdb 
```

## docker create
script is using `workdir` to read `config.ini` file and write some output files
You can config script to your needs by editing  initial `config.ini` file:
```bash
nano workdir/config.ini
```
To create docker container (and map workdir from outside). I'm not using `docker run` as it is not a container to run all the time:
```bash
docker create -v $PWD/workdir:/app/workdir --name=downsample_influxdb downsample_influxdb
```
[optional] Please note that with this setup `localhost` address will not be accesible, you need to specify IP address. This can be overcome with using host network inside contaner by adding `--net=host` to `docker create`

## docker start
To start scirpt use (**after updating `config.ini` to your needs**):
```bash
docker start downsample_influxdb
```
You can also attach STDOUT/STDERR and forward signals by adding `-a` flag to `docker start`


# Configuration
Configuration of this script is done through `config.ini` file in `wordir` directory.
Configuration is divided into parts:
## influxdb_connection
Definition of connection, address, port, user, password. Both IP address or DNS address can be used. 
See example `config.ini` for details and DEFAULT values.
## influxdb_db
Configuration of database name and source and target retention policies. 
Time range to downsample also can be configured for example to downsample only data from last week.
See example `config.ini` for details and DEFAULT values.

## downsample_mode
Configuration of how to do downsampling
Availble modes:
- simple_group_by_fullscan
- iterate_by_1h_window_measurements_only
- iterate_by_1h_window_series
See below for details

# Downsampling modes
All modes are selecting some data from source retention policy and insert int target retention policy. This is done through `select ... into` clause.
Each mode is different in terms of
- approach
- number of target datapoints
- time to execute

## simple_group_by_1d_fullscan
Full scan with group by on each measurement
 - agregates data by 1 day (mean, max, min) 
 - there is that fullscan can fail on bigger datasets (not tested yet, I don't know what influxdb engine will do)
 - it is based on `group by *` so can loose some data (particulary fields that are not tags and their mean value isn't miningful, for instnce strings and booleans, but also some numric identifiers)
 - **algorithm**:
```
for each measurements
    select mean(*), max(*), min(*)
    into rp_target 
    group by *, time(1d)
    note: field names are retained, so field named 'x' is not changed into 'mean_x' etc.
```
## iterate_by_1h_window_measurements_only
It's slower than full scan but no risk of OOM error - many small `select ... into`
-  iterates through measurements only (not by all disticn series in measurement), that's why it can ommit some series
- does not group, selects only first row by time window
- **algorithm**:
```
for each measurement
    for each 1h window
        select *
        into rp_target 
        limit 1 (takes only first row)
```

### iterate_by_1h_window_series
It's slower than full scan but no risk of OOM error - many small `select ... into`
- iterates through series 
- does not group, selects only first row by time window
- **algorithm**:
```
for each measurement
    for each series
        for each 1h window
            select *
            into rp_target 
            limit 1 (takes only first row)
```

# Downsampling modes comparision
Please note that performance of each mode strongly depends on your data structure, especialy number of datapoing, measurements and series.

For reference, here short test on my Raspberry Pi 3 B, quite idle as running only docker, telegraf, influxdb and grafana.
Test sample is influx database of telegraf data captured within last 14 days
DB with default settings, no continous queries, 20 measurements, ~250 series.
Size of original/source retention policy on disk ~20MB.

Test run results:
mode|select…into count|datapoins written count|time elapsed [HH:MM:SS]|size on disk [kB]
---|---:|---:|---:|---:
source|-|-|-|20 428
simple_group_by_fullscan|20|1 333|00:03:38| 1 860
iterate_by_1h_window_measurements_only|6 066|6 008|00:14:34| 328	
iterate_by_1h_window_series|26 610|26 247|01:04:14| 504

Note that simple_group_by_fullscan adds min and max data and other modes don't change (calculate mean) data just select existing rows/datapoints.
