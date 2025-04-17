import requests
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

url = 'https://leetcode.com/graphql'
headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_user_profile(username):
    query = """
    query getUserProfile($username: String!) {
      matchedUser(username: $username) {
        username
        submitStats: submitStatsGlobal {
          acSubmissionNum {
            difficulty
            count
            submissions
          }
        }
      }
    }
    """
    variables = {"username": username}
    payload = {"query": query, "variables": variables}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        data = response.json()
        return data['data']['matchedUser']['submitStats']['acSubmissionNum']
    return None

def get_user_ranking_and_contest(username):
    query = """
    query userPublicProfile($username: String!) {
      matchedUser(username: $username) {
        contestBadge {
          name
          expired
          hoverText
          icon
        }
        profile {
          ranking
        }
      }
    }
    """
    variables = {"username": username}
    payload = {"query": query, "variables": variables}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        data = response.json().get('data', {}).get('matchedUser', {})
        return {
            "ranking": data.get("profile", {}).get("ranking", "N/A"),
            "contest_badge": data.get("contestBadge", None)
        }
    return None

def get_language_wise_distribution(username):
    query = """
    query languageStats($username: String!) {
      matchedUser(username: $username) {
        languageProblemCount {
          languageName
          problemsSolved
        }
      }
    }
    """
    variables = {"username": username}
    payload = {"query": query, "variables": variables}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        data = response.json()
        return data['data']['matchedUser']['languageProblemCount']
    return None

def get_topic_wise_distribution(username):
    query = """
    query skillStats($username: String!) {
      matchedUser(username: $username) {
        tagProblemCounts {
          advanced {
            tagName
            problemsSolved
          }
          intermediate {
            tagName
            problemsSolved
          }
          fundamental {
            tagName
            problemsSolved
          }
        }
      }
    }
    """
    variables = {"username": username}
    payload = {"query": query, "variables": variables}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        data = response.json().get('data', {}).get('matchedUser', {}).get('tagProblemCounts', {})
        topic_distribution = {}
        for level in ["advanced", "intermediate", "fundamental"]:
            for topic in data.get(level, []):
                topic_distribution[topic["tagName"]] = topic["problemsSolved"]
        return topic_distribution
    return None

def get_recent_submissions(username):
    query = """
    query userProfileCalendar($username: String!) {
      matchedUser(username: $username) {
        userCalendar {
          submissionCalendar
        }
      }
    }
    """
    variables = {"username": username}
    payload = {"query": query, "variables": variables}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if response.status_code == 200:
        data = response.json()
        submission_calendar = json.loads(data['data']['matchedUser']['userCalendar']['submissionCalendar'])
        
        month_wise = defaultdict(int)
        week_wise = defaultdict(int)
        
        today = datetime.now(timezone.utc)
        twelve_months_ago = today - timedelta(days=365)
        
        for timestamp, count in submission_calendar.items():
            date = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            if date >= twelve_months_ago:
                month_key = date.strftime('%Y-%m')
                week_key = date.strftime('%Y-W%U')
                month_wise[month_key] += count
                week_wise[week_key] += count
                
        return {
            "monthly_submissions": dict(sorted(month_wise.items())),
            "weekly_submissions": dict(sorted(week_wise.items()))
        }
    return None

def get_user_about_me(username):
    query = """
    query userPublicProfile($username: String!) {
      matchedUser(username: $username) {
        profile {
          aboutMe
        }
      }
    }
    """
    variables = {"username": username}
    payload = {"query": query, "variables": variables}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        data = response.json()
        return data.get('data', {}).get('matchedUser', {}).get("profile", {}).get("aboutMe", "N/A")
    return None
