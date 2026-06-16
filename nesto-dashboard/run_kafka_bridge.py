"""Run the NESTO MongoDB -> Kafka bridge loop."""

import os

import kafka_bridge_plan


def main() -> None:
    os.environ.setdefault("KAFKA_ENABLED", "true")
    os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    os.environ.setdefault("KAFKA_CLIENT_ID", "nesto-dashboard")
    os.environ.setdefault("KAFKA_POLL_SECONDS", "5")
    print("Watching MongoDB collections:")
    print(", ".join(kafka_bridge_plan.KAFKA_COLLECTIONS))
    print()
    print("Publishing new events to Kafka topics...")
    kafka_bridge_plan.run_bridge_loop()


if __name__ == "__main__":
    main()
