import argparse
import random
import time

import httpx


def main() -> None:
    p = argparse.ArgumentParser(description="PulseGuard load generator")
    p.add_argument("--url", required=True, help="Target URL, e.g. http://127.0.0.1:8000/api/ping")
    p.add_argument("--clients", type=int, default=5, help="Number of distinct API keys")
    p.add_argument("--requests", type=int, default=250, help="Total requests to send")
    p.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between requests")
    args = p.parse_args()

    keys = [f"DEMO{i+1:03d}" for i in range(args.clients)]

    ok = 0
    limited = 0

    with httpx.Client(timeout=10.0) as client:
        start = time.time()
        for i in range(args.requests):
            k = random.choice(keys)
            r = client.get(args.url, headers={"x-api-key": k})
            if r.status_code == 200:
                ok += 1
            elif r.status_code == 429:
                limited += 1
            if args.sleep > 0:
                time.sleep(args.sleep)

        elapsed = max(0.001, time.time() - start)

    print("--- PulseGuard load test ---")
    print(f"URL: {args.url}")
    print(f"Clients: {args.clients}")
    print(f"Requests: {args.requests}")
    print(f"200 OK: {ok}")
    print(f"429 limited: {limited}")
    print(f"RPS: {args.requests/elapsed:.2f}")


if __name__ == "__main__":
    main()
