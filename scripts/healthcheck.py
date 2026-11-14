import os
import sys
import urllib.request


def main() -> int:
    url = os.getenv("HEALTHCHECK_URL", "http://localhost:8501/_stcore/health")
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status == 200:
                print("ok")
                return 0
    except Exception as exc:
        print(f"healthcheck failed: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
