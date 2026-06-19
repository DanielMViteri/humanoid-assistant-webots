"""Seed local Nesto Care authentication users in MongoDB."""

import auth_store


if __name__ == "__main__":
    auth_store.ensure_seed_auth_users()
    print("auth_users seed check complete")
