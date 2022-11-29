## Background

When running debezium I have hit a deserialization exception with the following stack trace:
```
org.apache.kafka.connect.errors.ConnectException: An exception occurred in the change event producer. This connector will be stopped.
    at io.debezium.pipeline.ErrorHandler.setProducerThrowable(ErrorHandler.java:50)
    at io.debezium.connector.mysql.MySqlStreamingChangeEventSource$ReaderThreadLifecycleListener.onEventDeserializationFailure(MySqlStreamingChangeEventSource.java:1247)
    at com.github.shyiko.mysql.binlog.BinaryLogClient.listenForEventPackets(BinaryLogClient.java:1064)
    at com.github.shyiko.mysql.binlog.BinaryLogClient.connect(BinaryLogClient.java:631)
    at com.github.shyiko.mysql.binlog.BinaryLogClient$7.run(BinaryLogClient.java:932)
    at java.base/java.lang.Thread.run(Thread.java:829)
Caused by: io.debezium.DebeziumException: Failed to deserialize data of EventHeaderV4{timestamp=1669665091000, eventType=EXT_WRITE_ROWS, serverId=1, headerLength=19, dataLength=8112, nextPosition=21550035, flags=0}
    at io.debezium.connector.mysql.MySqlStreamingChangeEventSource.wrap(MySqlStreamingChangeEventSource.java:1194)
    ... 5 more
Caused by: com.github.shyiko.mysql.binlog.event.deserialization.EventDataDeserializationException: Failed to deserialize data of EventHeaderV4{timestamp=1669665091000, eventType=EXT_WRITE_ROWS, serverId=1, headerLength=19, dataLength=8112, nextPosition=21550035, flags=0}
    at com.github.shyiko.mysql.binlog.event.deserialization.EventDeserializer.deserializeEventData(EventDeserializer.java:341)
    at com.github.shyiko.mysql.binlog.event.deserialization.EventDeserializer.nextEvent(EventDeserializer.java:244)
    at io.debezium.connector.mysql.MySqlStreamingChangeEventSource$1.nextEvent(MySqlStreamingChangeEventSource.java:230)
    at com.github.shyiko.mysql.binlog.BinaryLogClient.listenForEventPackets(BinaryLogClient.java:1051)
    ... 3 more
Caused by: com.github.shyiko.mysql.binlog.event.deserialization.MissingTableMapEventException: No TableMapEventData has been found for table id:116. Usually that means that you have started reading binary log 'within the logical event group' (e.g. from WRITE_ROWS and not proceeding TABLE_MAP
    at com.github.shyiko.mysql.binlog.event.deserialization.AbstractRowsEventDataDeserializer.deserializeRow(AbstractRowsEventDataDeserializer.java:109)
    at com.github.shyiko.mysql.binlog.event.deserialization.WriteRowsEventDataDeserializer.deserializeRows(WriteRowsEventDataDeserializer.java:64)
    at com.github.shyiko.mysql.binlog.event.deserialization.WriteRowsEventDataDeserializer.deserialize(WriteRowsEventDataDeserializer.java:56)
    at com.github.shyiko.mysql.binlog.event.deserialization.WriteRowsEventDataDeserializer.deserialize(WriteRowsEventDataDeserializer.java:32)
    at com.github.shyiko.mysql.binlog.event.deserialization.EventDeserializer.deserializeEventData(EventDeserializer.java:335)
    ... 6 more
```


After some digging I realized that the issue was some inefficient code in a SMT.  After fixing this, I haven't seen the error.  I was able to reproduce the issue by using a SMT that I have originally used as a template (https://github.com/cjmatta/kafka-connect-insert-uuid) and added a sleep statement of 50ms.  

It seems like include.query being set to true along with the large bulk insert query used in the python script seems to be the best way to reproduce this issue.

### Bring up Containers

```bash
DEBEZIUM_VERSION=1.9 docker-compose -f docker-compose-mysql.yaml up -d
```

Note: I have heard from people with M1 macs that the Kafka Connect image fails to build.

### Start Debezium
Shell into the kafka connect container:

```bash
docker exec -it <container id here> bash
```

Start Debezium:

```bash
curl -i -X PUT -H "Accept:application/json" -H  "Content-Type:application/json" localhost:8083/connectors/inventory-connector/config -d '
{
  "connector.class": "io.debezium.connector.mysql.MySqlConnector",
  "tasks.max": "1",
  "database.hostname": "mysql",
  "database.port": "3306",
  "database.user": "debezium",
  "database.password": "dbz",
  "database.server.id": "184054",
  "database.server.name": "dbserver1",
  "database.include.list": "inventory",
  "database.history.kafka.bootstrap.servers": "kafka:19092",
  "database.history.kafka.topic": "dbhistory.inventory",
  "snapshot.mode": "schema_only",
  "provide.transaction.metadata": "true",
  "key.converter": "org.apache.kafka.connect.json.JsonConverter",
  "key.converter.schemas.enable": "false",
  "value.converter": "org.apache.kafka.connect.json.JsonConverter",
  "value.converter.schemas.enable": "false",
  "include.query": "true",
  "transforms": "insertuuid",
  "transforms.insertuuid.type": "com.github.cjmatta.kafka.connect.smt.InsertUuid$Value",
  "transforms.insertuuid.uuid.field.name": "uuid"
}'
```

### Run Python script

Shell into Python container:

```bash
docker exec -it <container id here> bash
```

Run script:

```bash
python reproduce_deserialization_error.py
```

### Tail Kafka Connect logs

```bash
docker logs -f --tail 50 <container id here> 2>&1 | grep -v aaaaa
```

We grep -v the `aaaaa` string because the logs dump the most recent record which is a very long `aaaaa` string.

You should see the deserialization error after a minute or two.  The error will be immediately preceeded by the following logging:

```
Nov 28, 2022 10:47:09 PM com.github.shyiko.mysql.binlog.BinaryLogClient$5 run
INFO: Keepalive: Trying to restore lost connection to mysql:3306
```

which seems to suggest this is caused by MySQL closing the connection.

After 5-10 minutes you can check the status in the kafka connect container and see that the task has failed with the same deserialization error:

```
curl -XGET localhost:8083/connectors/inventory-connector/tasks/0/status
```
