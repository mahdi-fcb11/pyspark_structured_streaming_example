1 .create venv then install required packages. pip install -r requirements.txt
2. run: docker-compose up -d, confluent kafka image and kafka ui image will be downloaded. you can access kafka ui in localhost:8085
3. in kafka-ui topic section create a topic named test.user_events
4. run generate_msg.py to produce messages into kafka topic
5. run MySpark.py, it contains necessary dependencies, you can also submit an app to spark cluster: spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 MySpark.py 
