
import redis

REDIS_URL = "redis://localhost:6379/0"
PREFIX = "docsearch:"
SET_COMPLETED_FILE_IDS = f"{PREFIX}completed_file_ids"
FILE_ID = "1039"

def manual_remove():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    if r.sismember(SET_COMPLETED_FILE_IDS, FILE_ID):
        print(f"ID {FILE_ID} is in set. Removing...")
        r.srem(SET_COMPLETED_FILE_IDS, FILE_ID)
        print("Removed.")
    else:
        print(f"ID {FILE_ID} is NOT in set.")

    if r.sismember(SET_COMPLETED_FILE_IDS, FILE_ID):
        print("STILL IN SET!")
    else:
        print("Confirmed: NOT in set.")

if __name__ == "__main__":
    manual_remove()
