
import redis

def check_dbs():
    for db in range(16):
        try:
            r = redis.Redis(host='localhost', port=6379, db=db, decode_responses=True)
            count = r.dbsize()
            if count > 0:
                print(f"DB {db}: {count} keys")
                # Sample a key to see if it's docsearch
                keys = r.keys("docsearch:*")
                if keys:
                    print(f"  Contains {len(keys)} 'docsearch' keys.")
                    # Check for processing keys here
                    processing = r.keys("docsearch:processing:*")
                    if processing:
                         print(f"  Contains {len(processing)} processing keys!")
        except Exception as e:
            print(f"DB {db}: Error {e}")

if __name__ == "__main__":
    check_dbs()
