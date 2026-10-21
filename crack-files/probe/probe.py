import urllib.request

def check(url):
    # No scheme/host allow-list.
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status

def rule_matches(url):
    return check(url) < 500
