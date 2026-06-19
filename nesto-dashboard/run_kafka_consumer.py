"""Run the NESTO Kafka -> Redis dashboard consumer loop."""

import os

import kafka_bridge_plan


def main() -> None:
    os.environ.setdefault("KAFKA_ENABLED", "true")
    os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    os.environ.setdefault("KAFKA_CLIENT_ID", "nesto-dashboard")
    os.environ.setdefault("KAFKA_CONSUMER_GROUP", "nesto-dashboard-consumer")
    print("Listening to Kafka topics...")
    print(", ".join(kafka_bridge_plan.EXPECTED_TOPICS))
    kafka_bridge_plan.consume_kafka_events_loop()


if __name__ == "__main__":
    main()
