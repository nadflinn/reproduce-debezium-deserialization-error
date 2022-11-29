import mysql.connector


mydb = mysql.connector.connect(user='root', database='inventory', host='mysql', password='debezium')
cursor = mydb.cursor()

cursor.execute("create table IF NOT EXISTS test_table (`id` int(11) NOT NULL AUTO_INCREMENT, `mytextfield` mediumtext, `update_field` varchar(255), PRIMARY KEY (`id`))")
mydb.commit()


def get_batch_insert_query(number_of_records, size_of_text):
    return "INSERT INTO test_table (`mytextfield`, `update_field`) values {}".format("('{}', '{}'),".format("a" * size_of_text, 'abc') * number_of_records).strip(",")


for _ in range(1, 21):
    cursor.execute(get_batch_insert_query(number_of_records=1000, size_of_text=1000))
mydb.commit()
