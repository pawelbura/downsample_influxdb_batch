# downsample_influxdb_batch
python batch script to downsample influxdb database in a batch mode

### This script is inteded to be small, used from time to time and run in a batch mode.
### Script prepared to tun in docker container

### Other ways to look at
There are plenty of ways to do downsampling, for example the one suggested by influx:
 - use influxdb continuous query to insert downsampled data to another retention policy and configure original retention policy to be restricted to shorter time: https://docs.influxdata.com/influxdb/v1.8/guides/downsample_and_retain/ . But this needs to be done upfront.
 - From TICK stack, you can use Kapacitor, sample node, as described here: https://archive.docs.influxdata.com/kapacitor/v1.3/nodes/sample_node/ . But this is another comprehensive tool to configure.

# How to run
## docker build
to build docker image from code, execute:
```bash
docker build . -t downsample_influxdb 
```

## docker create
script is using `workdir` to read `config.ini` file and write some output files
To make a dir and copy there initial `config.ini` file:
```bash
mkdir workdir
wget -O workdir/config.ini https://raw.githubusercontent.com/pawelbura/downsample_influxdb_batch/main/app/config.ini
```

And update `confit.ini` to your needs.

To create docker container (and map workdir from outside). I'm not using `docker run` as it is not a container to run all the time:
```bash
docker create -v $PWD/workdir:/app/workdir --name=downsample_influxdb downsample_influxdb
```
[optional] Please note that with this setup `localhost` address will not be accesible, you need to specify IP address. This can be overcome with using host network inside contaner:
```bash
docker create --net=host -v $PWD/workdir:/app/workdir --name=downsample_influxdb downsample_influxdb
```

## docker start
And then it can be started whenever needed using (**after updating `config.ini` to your needs**):
```bash
docker start downsample_influxdb
```
