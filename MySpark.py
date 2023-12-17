import pyspark.sql
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, \
    TimestampType
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import timedelta, datetime

KAFKA_TOPIC_NAME = "test.user_events"
KAFKA_BOOTSTRAP_SERVERS = "localhost:9093"

spark = (
    SparkSession.builder.appName("Kafka Pyspark Streaming task")
    .config("spark.driver.host", "localhost")
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

SCHEMA1 = StructType([
    StructField("user_id", IntegerType()), StructField("response_time_ms", IntegerType()),
    StructField("endpoint", StringType()), StructField("created_at", TimestampType())])


def fraud_batch_process(batch_df: pyspark.sql.DataFrame, batch_id):
    if batch_df.count() > 0:
        print(f"Processing Batch {batch_id}")
        # batch_df.show(10, False)
        window_spec = Window().partitionBy("user_id").orderBy("created_at")
        batch_df_final = batch_df.withColumn("lag_value", F.lag("created_at").over(window_spec)) \
            .filter(F.col('lag_value').isNotNull())
        batch_df_final = batch_df_final.withColumn(
            'req_diff', (F.col('created_at').cast('double') - F.col('lag_value').cast('double'))) \
            .groupby('user_id').agg(F.round(F.stddev('req_diff').alias('std'), 4), F.count('req_diff'))

        if batch_df_final.count() > 0:
            batch_df_final.show(10, False)

            # persist data in parquet format
            # to store data in hdfs we should address hdfs namenode url
            # like hdfs://namenode:8020/pyspark/streaming/fraud.parquet
            batch_df_final.write.parquet('./fraud_parquet', mode='overwrite')


if __name__ == "__main__":
    # q1 read customers_birthdate.csv file, calculate age then filter out based on age
    df_sql = spark.read.csv('./customers_birthdate.csv', header=True, inferSchema=True)
    df_sql.printSchema()
    df_sql_final = df_sql.withColumn('age', (datetime.now().date() - F.col('birth_date')).cast('integer')) \
        .selectExpr('name', 'city', 'round(age / 365, 0) as age') \
        .filter(F.col('age') < 25)

    df_sql_final.show(15, False)
    df_sql_final.write.parquet('./parquet_dest', mode='overwrite')

    df = (spark
          .readStream
          .format("kafka")
          .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
          .option("subscribe", KAFKA_TOPIC_NAME)
          .option("startingOffsets", "earliest")
          .load()
          )

    df_initial = df.selectExpr("CAST(key AS STRING)", "CAST(value AS STRING)", "timestamp") \
        .select(F.from_json('value', SCHEMA1).alias("value")) \
        .select('value.*')

    # q2.1 calculate by sliding window in every hour with every 5 minutes sliding,
    # watermark is used to consider 30 min data late in producing section
    df_final_1 = df_initial.withWatermark('created_at', '30 minutes') \
        .groupby(
        F.window('created_at', "1 hour", '5 minutes'),
        df_initial.user_id
    ).count()

    # q2.2 calculate average of response time per user
    df_final_2 = df_initial.groupby(df_initial.user_id).agg(
        F.expr('count(*) as request_count'),
        F.expr("avg(response_time_ms) as avg_response_time")
    )

    # q2.3 filtering data based on fraud case described in generate_msg.py
    # dataframe will be processed in foreach batch before persisting.
    df_fraud = df_initial.filter(
        (F.col('created_at') > (datetime.now() - timedelta(minutes=2))) & \
        (F.col('endpoint').isin(['/property_detail', '/contact_owner']))
    ).groupby(
        df_initial.user_id, df_initial.created_at
    ).count()

    # for q2.1 and q2.2 data processing triggers every 30 seconds
    df_final_1.writeStream \
        .format("console") \
        .option('truncate', 'false') \
        .outputMode("complete") \
        .trigger(processingTime="30 seconds") \
        .start()

    df_final_2.writeStream \
        .format("console") \
        .option('truncate', 'false') \
        .outputMode("complete") \
        .trigger(processingTime="30 seconds") \
        .start()

    # this section triggers for every arriving data
    df_fraud.writeStream \
        .outputMode("complete") \
        .foreachBatch(fraud_batch_process) \
        .start() \
        .awaitTermination()

