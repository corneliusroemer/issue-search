# %%
import json
import os

import pandas as pd
import requests
from algoliasearch.search.client import SearchClientSync
from dotenv import load_dotenv

load_dotenv()

# %%
# Replace with your repository details and personal access token
owner = "loculus-project"
repo = "loculus"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_API_KEY")
INDEX_NAME = os.getenv("ALGOLIA_INDEX_NAME")

#%%
def fetch_issues(owner=owner,repo=repo,max_pages=None) -> list[dict]:
    accept = "application/vnd.github.text+json"
    auth_header = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    headers = {"Accept": accept, **auth_header}
    params = {"state": "all", "per_page": 100}  # max

    issues = []
    page = 1

    while max_pages is None or page <= max_pages:
        print(f"Fetching page {page}")
        params["page"] = page
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            headers=headers,
            params=params,
        )
        data = response.json()
        if not data:
            break
        issues.extend(data)
        page += 1

    print(f"Total issues fetched: {len(issues)}")
    return issues

#%%
def write_issues_to_file(issues, filename="issues.json"):
    with open(filename, "w") as file:
        json.dump(issues, file, indent=2)

#%%
def read_issues_from_file(filename="issues.json") -> list[dict]:
    with open(filename, "r") as file:
        return json.load(file)

# %%
def get_truncated_body(issue) -> str:
    # Attributes for body
    ATTRIBUTES = ["body_text", "body"]
    # Get first non-empty attribute
    body = next((issue.get(attr) for attr in ATTRIBUTES if issue.get(attr)), None)
    if body:
        return body[:2000]
    return ""

def labels(i) -> list[str]:
    labels = set()
    try:
        for label in i.get("labels"):
            if isinstance(label, dict):
                if label_name := label.get("name"):
                    labels.add(label_name)
    except Exception as e:
        print(i.get("labels"))
        print(f"Error: {e}")
    if "pull_request" in i:
        labels.add("pull_request")
    else:
        labels.add("issue")
    if state := i.get("state"):
        labels.add(state)
    if i.get("state_reason") is not None:
        labels.add(i["state_reason"])
    if i.get("draft", False):
        labels.add("draft")
    return list(labels)


def date_to_unix(date) -> int:
    if not date:
        return None
    return int(pd.to_datetime(date).timestamp())


def type_of_issue(i) -> str:
    if "pull_request" in i:
        return "pull_request"
    return "issue"


# %%

def format_issues(issues: list[dict], extra_keyvals: dict = {}) -> list[dict]:
    formatted_issues = []

    for issue in issues:
        formatted_issue = {
            "objectID": issue["id"],  # Unique identifier
            "number": issue["number"],
            "title": issue["title"],
            "body": get_truncated_body(issue),
            "state": issue["state"],
            "labels": labels(issue),
            "created_at": date_to_unix(issue["created_at"]),
            "updated_at": date_to_unix(issue["updated_at"]),
            "closed_at": date_to_unix(issue.get("closed_at")),
            "user": issue["user"]["login"],
            "url": issue["html_url"],
            "comments": issue["comments"],
            "reactions": issue["reactions"]["total_count"],
            "type": type_of_issue(issue),
            **extra_keyvals,
        }
        formatted_issues.append(formatted_issue)

    print(f"Total formatted issues: {len(formatted_issues)}")
    return formatted_issues

# Upload the formatted issues to Algolia
#%%
def upload_issues_to_algolia(formatted_issues: list[dict]):
    # Initialize the client
    client = SearchClientSync(ALGOLIA_APP_ID, ALGOLIA_API_KEY)
    index_name = INDEX_NAME

    # Save all objects to the index
    save_resp = client.save_objects(
        index_name=index_name,
        objects=formatted_issues,
    )

    # Wait until indexing is complete
    for response in save_resp:
        client.wait_for_task(index_name, response.task_id)

    print("Data successfully imported into Algolia.")

# %%

repos: list[dict] = [
    {"owner": "loculus-project", "repo": "loculus", "keyvals": {"repo": "loculus"}},
    {"owner": "pathoplexus", "repo": "pathoplexus", "keyvals": {"repo": "pathoplexus"}},
]

if __name__ == "__main__":
    to_upload = []
    for repo in repos:
        issues = fetch_issues(owner=repo["owner"],repo=repo["repo"], max_pages=50)
        to_upload.extend(format_issues(issues, repo["keyvals"]))
    write_issues_to_file(to_upload, "to_upload.json")
    upload_issues_to_algolia(to_upload)

# %%
