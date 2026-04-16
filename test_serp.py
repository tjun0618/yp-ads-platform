import requests
import json

# Test Google SERP API
url = "http://localhost:5055/api/workflow/google_serp/362447"
response = requests.post(url)
result = {
    "status": response.status_code,
    "response": response.json()
}

with open("test_result.json", "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("Done")
