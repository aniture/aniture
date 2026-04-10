import requests
import json
import os
from datetime import datetime, timedelta, timezone

USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER") or os.environ.get("GH_USERNAME")
if not USERNAME:
    raise SystemExit("Could not determine GitHub username. Set GH_USERNAME env var.")
PAT = os.environ.get("GH_PAT")
TOKEN = PAT or os.environ.get("GITHUB_TOKEN")
DAYS_BACK = int(os.environ.get("DAYS_BACK", "1"))


headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

log_file = "loc-log.json"
try:
    with open(log_file) as f:
        log = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    log = []

today = datetime.now(timezone.utc)
dates = [
    (today - timedelta(days=i)).strftime("%Y-%m-%d")
    for i in range(1, DAYS_BACK + 1)
]

for date in dates:
    print(f"\n--- {date} ---")

    search_url = "https://api.github.com/search/issues"
    params = {
        "q": f"author:{USERNAME} type:pr is:merged merged:{date}",
        "per_page": 100
    }

    response = requests.get(search_url, headers=headers, params=params)
    data = response.json()

    total_additions = 0
    total_deletions = 0
    prs_processed = []

    for item in data.get("items", []):
        pr_number = item["number"]
        pr_url = item["url"].replace("/issues/", "/pulls/")
        pr_response = requests.get(pr_url, headers=headers)

        if pr_response.status_code == 200:
            pr_data = pr_response.json()
            repo_full_name = pr_data["base"]["repo"]["full_name"]

            # Fetch files to exclude docs (.md, .rst, .txt)
            EXCLUDE_EXTS = {".md", ".rst", ".txt"}
            files_url = pr_url + "/files"
            additions, deletions = 0, 0
            page = 1
            while True:
                files_resp = requests.get(files_url, headers=headers, params={"per_page": 100, "page": page})
                files = files_resp.json()
                if not files:
                    break
                for f in files:
                    ext = "." + f["filename"].rsplit(".", 1)[-1] if "." in f["filename"] else ""
                    if ext.lower() not in EXCLUDE_EXTS:
                        additions += f.get("additions", 0)
                        deletions += f.get("deletions", 0)
                if len(files) < 100:
                    break
                page += 1

            total_additions += additions
            total_deletions += deletions
            prs_processed.append({
                "repo": repo_full_name,
                "pr": pr_number,
                "title": item["title"],
                "additions": additions,
                "deletions": deletions
            })
            print(f"  PR #{pr_number} in {repo_full_name}: +{additions} -{deletions}")

    if not prs_processed:
        print("  No merged PRs found")

    print(f"  Total: +{total_additions} -{total_deletions} (net {total_additions - total_deletions})")

    entry = {
        "date": date,
        "additions": total_additions,
        "deletions": total_deletions,
        "net": total_additions - total_deletions,
        "prs": prs_processed
    }

    existing = next((e for e in log if e["date"] == date), None)
    if existing:
        existing.update(entry)
    else:
        log.append(entry)

log.sort(key=lambda x: x["date"])

with open(log_file, "w") as f:
    json.dump(log, f, indent=2)

print(f"\nLog saved to {log_file} ({len(log)} total entries)")
