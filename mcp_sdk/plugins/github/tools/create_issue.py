def create_issue(title: str, body: str) -> dict[str, str]:
    """
    Create a new GitHub issue.
    """
    print(f"Creating GitHub issue: {title}")
    return {"status": "created", "title": title}
