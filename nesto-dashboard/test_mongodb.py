"""
MongoDB connection test.

What it does:
  1. Reads the connection string from the .env file (keeps secrets out of code)
  2. Tries to connect to the cluster and "ping" it
  3. Lists the databases it can see
  4. Checks that the project database (humanoid_assistant) is reachable

Run with:  python test_mongodb.py

This is a one-off check, not part of the app. It just answers the question:
"Can my machine actually reach Clara's MongoDB cluster?"
"""

import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

# Name of the project database we expect to find on the cluster.
EXPECTED_DB = "humanoid_assistant"


def main():
    # 1. Load the .env file so MONGODB_URI becomes available
    load_dotenv()
    uri = os.getenv("MONGODB_URI")

    if not uri:
        print("FAIL: No MONGODB_URI found.")
        print("Check that a .env file exists in this folder and contains a line")
        print("starting with MONGODB_URI=")
        sys.exit(1)

    print("Found MONGODB_URI in .env. Attempting to connect...")

    # 2. Create the client. serverSelectionTimeoutMS keeps it from hanging
    #    forever if the cluster is unreachable; it gives up after 5 seconds.
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # The ping command is the simplest way to confirm a live connection.
        client.admin.command("ping")
        print("PASS: Connected to the cluster successfully (ping OK).")
    except ServerSelectionTimeoutError:
        print("FAIL: Could not reach the cluster within 5 seconds.")
        print("Most common causes:")
        print("  - Your current IP address is not on the cluster's Network Access allow-list")
        print("    (ask Clara to add your IP, or temporarily allow 0.0.0.0/0 for testing).")
        print("  - No internet connection.")
        sys.exit(1)
    except OperationFailure:
        print("FAIL: Reached the cluster, but authentication was rejected.")
        print("This usually means the username or password in your connection string is wrong.")
        sys.exit(1)
    except ConfigurationError as err:
        print("FAIL: The connection string looks malformed.")
        print(f"Details: {err}")
        sys.exit(1)
    except Exception as err:
        print(f"FAIL: Unexpected error: {type(err).__name__}: {err}")
        sys.exit(1)

    # 3. List the databases we can see (read-only, harmless)
    try:
        db_names = client.list_database_names()
        print(f"Databases visible to this account: {db_names}")
    except OperationFailure:
        # Some restricted users can connect but cannot list all databases.
        # That is not a failure for our purposes.
        db_names = []
        print("Note: connected, but this account is not allowed to list all databases.")
        print("That is fine, it just means limited permissions.")

    # 4. Check the project database specifically
    if EXPECTED_DB in db_names:
        db = client[EXPECTED_DB]
        collections = db.list_collection_names()
        print(f"PASS: Found the '{EXPECTED_DB}' database.")
        print(f"Collections inside it: {collections if collections else '(none yet)'}")
    else:
        # The database may simply not have data yet, or the account cannot list it.
        # We can still reference it; it gets created on first write.
        print(f"Note: '{EXPECTED_DB}' did not appear in the list above.")
        print("That is normal if no data has been written to it yet, or if this")
        print("account has limited listing permissions. The connection itself works.")

    client.close()
    print("Done. Connection test complete.")


if __name__ == "__main__":
    main()