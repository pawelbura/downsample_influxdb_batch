# downsample_influxdb_batch
python batch script to downsample influxdb database in a batch mode

### This script is inteded to be small, used from time to time and run in a batch mode.
### Script prepared to tun in docker container

### Other ways
There are plenty of ways to do downsampling, for example the one suggested by influx:
 - use influxdb continuous query to insert downsampled data to another retention policy and configure original retention policy to be restricted to shorter time: 
 https://docs.influxdata.com/influxdb/v1.8/guides/downsample_and_retain/
 
But this needs to be done upfront.

From TICK stack, you can use Kapacitor:
  - sample node, as described here:
  https://archive.docs.influxdata.com/kapacitor/v1.3/nodes/sample_node/

But this is another comprehensive tool to configure.


# docker build
to build docker image from code, execute:
```bash
docker build . -t downsample_influxdb 
```
