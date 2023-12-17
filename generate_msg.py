import random
from confluent_kafka import Producer
from datetime import datetime, timedelta
import json
import time

producer = Producer({
    'bootstrap.servers': "localhost:9093",
    'delivery.timeout.ms': 30000,
    'acks': 'all'
})

topic = 'test.user_events'
endpoints = [
    '/properties', '/property_detail', '/contact_owner', '/'
]

if __name__ == "__main__":
    counter_ = 0
    while True:
        user_id = random.randint(1, 30)
        random_created_at = datetime.now() + timedelta(minutes=random.randint(-30, 0))
        msg = {
            'user_id': user_id,
            'response_time_ms': random.randint(20, 700),
            'endpoint': random.choice(endpoints),
            'created_at': str(random_created_at)
        }
        producer.produce(topic, key=str(user_id), value=json.dumps(msg))
        print(msg)

        # fraud generator, find crawler user, this user is crawling the website, he develops code
        # to request the website every 2 seconds, he just requests the property details and the contact_owner endpoint

        msg = {
            'user_id': 31,
            'response_time_ms': random.randint(20, 700),
            'endpoint': endpoints[2] if counter_ % 2 else endpoints[1],
            'created_at': str(datetime.now())
        }
        producer.produce(topic, key=str(user_id), value=json.dumps(msg))
        print(msg)
        counter_ += 1
        time.sleep(1)
        producer.poll(1)
