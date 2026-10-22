import os
import subprocess
import sys
import json

# client_id = os.environ.get("COMMERCETOOLS_CLIENT_ID")
client_id = "LZgc_kewdTnIPnFn7HOPyaud"
# client_secret = os.environ.get("COMMERCETOOLS_CLIENT_SECRET")
client_secret = "Lb6u1YwrP5nIGiQLz0KFmszvMKXzzXo8"

print("client_id:", client_id)
print("client_secret:", client_secret)



if not client_id or not client_secret:
    sys.exit("Set COMMERCETOOLS_CLIENT_ID and COMMERCETOOLS_CLIENT_SECRET first.")

result = subprocess.run(
    [
        "curl.exe", "-sS", "-X", "POST",
        "https://auth.us-east-2.aws.commercetools.com/oauth/token",
        "--basic", "--user", f"{client_id}:{client_secret}",
        "-d", "grant_type=client_credentials&scope=view_products:aurra_etl_connectors",
    ],
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.returncode:
    print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)

try:
    access_token = json.loads(result.stdout)["access_token"]
except (json.JSONDecodeError, KeyError) as exc:
    sys.exit(f"Could not read access token from response: {exc}")

products_result = subprocess.run(
    [
        "curl.exe", "-sS", "--get",
        "https://api.us-east-2.aws.commercetools.com/aurra_etl_connectors/products",
        "--header", f"Authorization: Bearer {access_token}",
        "--data-urlencode", "limit=5",
    ],
    capture_output=True,
    text=True,
)
if products_result.returncode:
    print(products_result.stderr, file=sys.stderr)
    sys.exit(products_result.returncode)

print("Products:")
print(products_result.stdout)
