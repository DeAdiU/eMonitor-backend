import requests
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import time 

CODEFORCES_API_URL = 'https://codeforces.com/api/'
CF_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def _fetch_codeforces_api(endpoint, params):
    """Helper to fetch data from Codeforces API and handle basic errors."""
    try:
        response = requests.get(f"{CODEFORCES_API_URL}{endpoint}", params=params, headers=CF_HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'OK':
            return data.get('result')
        else:
            print(f"Codeforces API Error ({endpoint}): {data.get('comment', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed for {endpoint}: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Failed to decode JSON response for {endpoint}")
        return None

def get_cf_user_submissions(handle, count=1000):
    """
    Fetches a specified number of recent submissions for a Codeforces user.
    Note: For full analysis, pagination might be needed for users with > 'count' submissions.
    """
    params = {"handle": handle, "count": count}
    return _fetch_codeforces_api("user.status", params)


def get_cf_user_info(handle):
    """
    Fetches basic user info including rating, rank, max rating/rank, and profile details.
    Maps to LeetCode's get_user_ranking_and_contest and get_user_about_me.
    """
    params = {"handles": handle}
    result = _fetch_codeforces_api("user.info", params)
    if result and isinstance(result, list) and len(result) > 0:
        user_info = result[0]
        return {
            "handle": user_info.get("handle"),
            "rating": user_info.get("rating"),
            "maxRating": user_info.get("maxRating"),
            "rank": user_info.get("rank"),
            "maxRank": user_info.get("maxRank"),
            "firstName": user_info.get("firstName"),
            "lastName": user_info.get("lastName"),
            "country": user_info.get("country"),
            "city": user_info.get("city"),
            "organization": user_info.get("organization"),
            "avatar": user_info.get("avatar"),
            "titlePhoto": user_info.get("titlePhoto"),
        }
    return None

def get_cf_solved_counts(handle, submission_limit=1000):
    """
    Calculates the number of unique problems solved by difficulty (rating).
    Maps to LeetCode's get_user_profile (submitStats).
    Difficulty based on problem rating (adjust thresholds as needed):
        - Easy: < 1200
        - Medium: 1200 - 1599
        - Hard: 1600 - 1899
        - Very Hard: 1900 - 2399
        - Expert: >= 2400
        - Unrated: No rating available
    """
    submissions = get_cf_user_submissions(handle, count=submission_limit)
    if submissions is None:
        return None

    solved_problems = set()
    counts = {
        "Easy": {"count": 0, "submissions": 0},
        "Medium": {"count": 0, "submissions": 0},
        "Hard": {"count": 0, "submissions": 0},
        "Very Hard": {"count": 0, "submissions": 0},
        "Expert": {"count": 0, "submissions": 0},
        "Unrated": {"count": 0, "submissions": 0},
        "All": {"count": 0, "submissions": 0}
    }
    total_ac_submissions = 0

    for sub in submissions:
        if sub.get('verdict') == 'OK':
            total_ac_submissions += 1
            problem = sub.get('problem', {})
            problem_id = f"{problem.get('contestId')}-{problem.get('index')}"
            
            if problem_id not in solved_problems:
                solved_problems.add(problem_id)
                rating = problem.get('rating')
                difficulty = "Unrated" 
                if rating is not None:
                    if rating < 1200: difficulty = "Easy"
                    elif rating < 1600: difficulty = "Medium"
                    elif rating < 1900: difficulty = "Hard"
                    elif rating < 2400: difficulty = "Very Hard"
                    else: difficulty = "Expert"

                if difficulty in counts:
                    counts[difficulty]["count"] += 1
                else:
                     counts["Unrated"]["count"] += 1

    counts["All"]["count"] = len(solved_problems)
    counts["All"]["submissions"] = total_ac_submissions 

    ac_submissions_by_cat = defaultdict(int)
    for sub in submissions:
        if sub.get('verdict') == 'OK':
            problem = sub.get('problem', {})
            rating = problem.get('rating')
            difficulty = "Unrated"
            if rating is not None:
                if rating < 1200: difficulty = "Easy"
                elif rating < 1600: difficulty = "Medium"
                elif rating < 1900: difficulty = "Hard"
                elif rating < 2400: difficulty = "Very Hard"
                else: difficulty = "Expert"
            ac_submissions_by_cat[difficulty] += 1

    for diff_key in counts:
        if diff_key != "All":
            counts[diff_key]["submissions"] = ac_submissions_by_cat.get(diff_key, 0)

    return counts


def get_cf_language_distribution(handle, submission_limit=1000):
    """
    Gets the distribution of programming languages used for accepted submissions
    on unique problems. Maps to LeetCode's get_language_wise_distribution.
    """
    submissions = get_cf_user_submissions(handle, count=submission_limit)
    if submissions is None:
        return None

    language_counts = defaultdict(int)
    solved_problems = set()

    for sub in submissions:
        if sub.get('verdict') == 'OK':
            problem = sub.get('problem', {})
            problem_id = f"{problem.get('contestId')}-{problem.get('index')}"
            language = sub.get('programmingLanguage')

            if problem_id not in solved_problems and language:
                solved_problems.add(problem_id)
                language_counts[language] += 1

    return dict(sorted(language_counts.items(), key=lambda item: item[1], reverse=True))


def get_cf_tag_distribution(handle, submission_limit=1000):
    """
    Gets the distribution of problem tags for accepted submissions on unique problems.
    Maps to LeetCode's get_topic_wise_distribution.
    """
    submissions = get_cf_user_submissions(handle, count=submission_limit)
    if submissions is None:
        return None

    tag_counts = defaultdict(int)
    solved_problems = set()

    for sub in submissions:
        if sub.get('verdict') == 'OK':
            problem = sub.get('problem', {})
            problem_id = f"{problem.get('contestId')}-{problem.get('index')}"
            tags = problem.get('tags', [])

            if problem_id not in solved_problems:
                solved_problems.add(problem_id)
                for tag in tags:
                    tag_counts[tag] += 1

    # Convert to list format similar to LeetCode if needed
    # return [{"tagName": tag, "problemsSolved": count} for tag, count in tag_counts.items()]
    return dict(sorted(tag_counts.items(), key=lambda item: item[1], reverse=True))


def get_cf_submission_calendar(handle, submission_limit=5000):
    """
    Generates monthly and weekly submission counts based on user's recent submissions.
    Maps to LeetCode's get_recent_submissions.
    Fetches more submissions by default for better calendar density.
    """
    submissions = get_cf_user_submissions(handle, count=submission_limit)
    if submissions is None:
        return None

    month_wise = defaultdict(int)
    week_wise = defaultdict(int)
    today = datetime.now(timezone.utc)
    one_year_ago = today - timedelta(days=365)

    for sub in submissions:
        timestamp = sub.get('creationTimeSeconds')
        if timestamp:
            sub_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            if sub_date >= one_year_ago:
                month_key = sub_date.strftime('%Y-%m')
                week_key = sub_date.strftime('%Y-W%U')
                month_wise[month_key] += 1
                week_wise[week_key] += 1

    return {
        "monthly_submissions": dict(sorted(month_wise.items())),
        "weekly_submissions": dict(sorted(week_wise.items()))
    }

def get_cf_rating_history(handle):
    """
    Fetches the user's rating change history.
    """
    params = {"handle": handle}
    result = _fetch_codeforces_api("user.rating", params)
    if result and isinstance(result, list):
        history = []
        for change in result:
            timestamp = change.get('ratingUpdateTimeSeconds')
            if timestamp:
                history.append({
                    "contestId": change.get('contestId'),
                    "contestName": change.get('contestName'),
                    "rank": change.get('rank'),
                    "timeSeconds": timestamp,
                    "timeFormatted": datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    "oldRating": change.get('oldRating'),
                    "newRating": change.get('newRating')
                })
        return history
    return None

