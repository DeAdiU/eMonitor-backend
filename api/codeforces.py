import requests
import time
import random
from datetime import datetime, timezone, timedelta
import json
import os
import google.generativeai as genai
import logging

from typing import Optional, List, Dict, Any, Tuple


CODEFORCES_API_BASE_URL = "https://codeforces.com/api/"
API_CALL_DELAY_SECONDS = 1
SUBMISSION_BATCH_SIZE = 10


try:
    GOOGLE_API_KEY = "AIzaSyAYjACuvYcuU_hAa0jI_VHhgX7uiGEcV3E"
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=GOOGLE_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel('gemini-1.5-flash')
    # print("Gemini API configured successfully.") 
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    print("AI Evaluation will use fallback logic.")
    GEMINI_MODEL = None


def _make_api_request(method_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if params is None:
        params = {}
    url = f"{CODEFORCES_API_BASE_URL}{method_name}"
    time.sleep(API_CALL_DELAY_SECONDS)
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "OK":
            return data.get("result", [] if method_name == "user.status" else {})
        else:
            error_comment = data.get('comment', 'Unknown Codeforces API error')
            raise ValueError(f"Codeforces API Error: {error_comment}")
    except requests.exceptions.Timeout:
        print(f"Warning: API request timed out for {method_name}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Error during API request to {method_name}: {e}")
        raise
    except ValueError as e:
        print(f"Error processing API response from {method_name}: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error during API request/processing for {method_name}: {e}")
        raise


def evaluate_submission_with_gemini(
    submission_details: Dict[str, Any],
    preferred_criteria_str: str
) -> Dict[str, Any]:
    # print("\n" + "-" * 20) # Removed print
    # print(f"Attempting AI Evaluation using Gemini:") 
    # print(f"  Submission ID: {submission_details.get('id')}") 

    if not GEMINI_MODEL:
        print("  Gemini API not available. Using fallback evaluation.")
        return evaluate_submission_fallback(submission_details, preferred_criteria_str)

    try:
        submission_details_json = json.dumps(submission_details, indent=2)
    except Exception as e:
        print(f"  Error converting submission details to JSON: {e}. Using basic info.") 
        submission_details_json = json.dumps({
            "id": submission_details.get("id"),
            "contestId": submission_details.get("contestId"),
            "problem": submission_details.get("problem"),
            "author": submission_details.get("author"),
            "programmingLanguage": submission_details.get("programmingLanguage"),
            "verdict": submission_details.get("verdict"),
            "passedTestCount": submission_details.get("passedTestCount"),
            "timeConsumedMillis": submission_details.get("timeConsumedMillis"),
            "memoryConsumedBytes": submission_details.get("memoryConsumedBytes"),
            "plagiarismVerdict": submission_details.get("plagiarismVerdict")
        }, indent=2)
    print(submission_details)
    print(submission_details_json)

    prompt = f"""
You are an AI assistant evaluating Codeforces/CodeChef submissions based ONLY on provided metadata and user preferences. You CANNOT see the actual source code.

**Submission Metadata:**
```json
{submission_details_json}

    

IGNORE_WHEN_COPYING_START
Use code with caution. Python
IGNORE_WHEN_COPYING_END

(The JSON above should now include a "plagiarismScore" key, e.g., "plagiarismScore": 15)

User Preference Criteria:
"{preferred_criteria_str}"

Evaluation Task:
Based only on the metadata and preferences above, provide an evaluation score (a single number between 0 and 100) and constructive feedback (a string). Consider the following guidelines derived from the user preference "{preferred_criteria_str}":

      
1. Verdict: This is the most important factor for initial scoring, but can be overridden by plagiarism.
    - If verdict is "OK" (or "AC"): Base score should be higher (e.g., start around 70). Evaluate further based on other criteria below.
    - If verdict is not "OK" (e.g., "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "COMPILATION_ERROR", "RUNTIME_ERROR"): The score MUST be significantly lower (e.g., 5-40 range).
        - If passedTestCount is available and greater than 0, give slightly more points within the low range (e.g., 15 + passedTestCount). Max score for non-OK should still be low (e.g., capped at 40 *before* considering plagiarism).
        - If passedTestCount is 0 or unavailable for a non-OK verdict, assign a very low score (e.g., 5-15 *before* considering plagiarism).
        - Mention the specific failure verdict and passedTestCount (if applicable) in the feedback.

2. Plagiarism Score: Check the `plagiarismScore` field (0-100, higher means more similar to other submissions). This factor has high priority.
    - If `plagiarismScore` is high (e.g., > 70): Assign a very low final score (e.g., 0-10), regardless of verdict or other factors. The feedback MUST prioritize and state "High plagiarism suspected (Score: [plagiarismScore])" or similar.
    - If `plagiarismScore` is moderate (e.g., 30-70): Apply a significant penalty to the score calculated from other factors (e.g., reduce score by 40-60 points, ensuring it doesn't go below 5-10). Feedback should clearly mention "Moderate similarity to other submissions found (Score: [plagiarismScore])".
    - If `plagiarismScore` is low (e.g., 10-30): Apply a small penalty (e.g., -5 to -10 points from the score calculated based on other factors). Feedback can mention "Minor code similarities found (Score: [plagiarismScore])".
    - If `plagiarismScore` is very low (e.g., < 10): No penalty for plagiarism. Feedback can optionally mention "Code appears original" if the verdict was also OK.

3. Language Preference (User wants C++ or Python or Java) but if {preferred_criteria_str} is saying any language use that if not mention then the bracket language: (Apply *before* plagiarism penalty, except if plagiarism is high)
    - Check `programmingLanguage`.
    - If it's C++ (any version) or Python/PyPy or Java: Award bonus points (e.g., +10-15) ONLY if the verdict is "OK".
    - If it's another language: Award fewer or no language bonus points.

4. Time Complexity Preference (User wants "less time complexity"): (Apply *before* plagiarism penalty, except if plagiarism is high)
    - Infer efficiency from `timeConsumedMillis` ONLY IF verdict is "OK". Lower time is better.
    - Very Low Time (e.g., < 200ms): Add bonus points (e.g., +10).
    - Moderate Time (e.g., 200ms - 1000ms): Add smaller bonus points (e.g., +5).
    - High Time (e.g., > 1000ms): Add no points or potentially deduct slightly (-5). Mention the time in feedback relative to the preference.
    - Ignore time score if verdict is not "OK".

5. Memory Usage: (Apply *before* plagiarism penalty, except if plagiarism is high)
    - Consider `memoryConsumedBytes` ONLY IF verdict is "OK". Lower memory is generally good but less prioritized unless mentioned in criteria.
    - Very Low Memory (e.g., < 65536 KB): Add small bonus (e.g., +3).
    - Moderate/High Memory: Neutral or tiny penalty.

6. Final Score Calculation:
    - Start with base score from Verdict.
    - Add/subtract points based on Language, Time, Memory (if verdict is OK).
    - Apply Plagiarism penalty based on its score range. This penalty can drastically reduce or override the score from other factors.
    - Ensure the final score is clamped between 0 and 100.

    

IGNORE_WHEN_COPYING_START
Use code with caution.
IGNORE_WHEN_COPYING_END

Output Format:
Return ONLY a valid JSON object with exactly two keys: "score" (a number between 0 and 100) and "feedback" (a string). Do not include ```json markdown delimiters around the final JSON output.

Example for OK (Low Plag): {{"score": 78, "feedback": "Good submission (OK Verdict). Used preferred language (C++). Excellent time performance (150ms). Minor code similarities found (Plag Score: 12)."}}
Example for WA (High Plag): {{"score": 5, "feedback": "High plagiarism suspected (Score: 85). Submission also failed: WRONG_ANSWER on test 3 (Passed 2 tests)."}}
Example for OK (High Plag): {{"score": 8, "feedback": "High plagiarism suspected (Score: 92), overriding correctness. Verdict was OK, but similarity is too high."}}
Example for TLE (Moderate Plag): {{"score": 10, "feedback": "Moderate similarity to other submissions found (Plag Score: 45). Submission also failed: TIME_LIMIT_EXCEEDED on test 5 (Passed 4 tests)."}}

Now, evaluate the provided submission based only on the metadata (including plagiarismScore) and preferences. Generate the JSON output."""

    try:
        response = GEMINI_MODEL.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.5
            )
            )

        cleaned_response_text = response.text.strip().strip('```json').strip('```').strip()
        result = json.loads(cleaned_response_text)

        if isinstance(result, dict) and "score" in result and "feedback" in result:
            try:
                score = float(result["score"])
                result["score"] = max(0.0, min(100.0, score))
            except (ValueError, TypeError):
                print("  Warning: Gemini returned non-numeric score. Using fallback.") 
                return evaluate_submission_fallback(submission_details, preferred_criteria_str)

            print(f"  Gemini Evaluation Result: Score={result['score']:.2f}") 
            print("-" * 20) # Removed print
            result["full_submission_details"] = submission_details
            return result
        else:
            # print("  Warning: Gemini response did not match expected JSON format. Using fallback.") 
            # print(f"  Received: {cleaned_response_text}")
            return evaluate_submission_fallback(submission_details, preferred_criteria_str)

    except json.JSONDecodeError as e:
        print(f"  Error: Failed to decode JSON response from Gemini: {e}") 
        print(f"  Received text: {response.text if 'response' in locals() else 'N/A'}") 
        print("  Using fallback evaluation.") 
        return evaluate_submission_fallback(submission_details, preferred_criteria_str)
    except Exception as e:
        # print(f"  An error occurred during Gemini API call: {e}") 
        # print("  Using fallback evaluation.") 
        return evaluate_submission_fallback(submission_details, preferred_criteria_str)

def evaluate_submission_fallback(
submission_details: Dict[str, Any],
preferred_criteria_str: str
) -> Dict[str, Any]:
# print(" Executing Fallback Evaluation Logic...") 
    score = 0.0
    feedback_lines = [f"Fallback evaluation for submission {submission_details.get('id')}:"]
    verdict = submission_details.get("verdict", "UNKNOWN")
    passed_tests = submission_details.get("passedTestCount", 0)
    lang = submission_details.get('programmingLanguage', '').lower()
    time_ms = submission_details.get('timeConsumedMillis', 9999)
    memory_kb = submission_details.get('memoryConsumedBytes', 99999999) / 1024
    preferred_langs = ["c++", "python", "pypy"]
    prefers_low_time = "less timecomplexity" in preferred_criteria_str.lower()

    if verdict == "OK":
        score = 70.0
        feedback_lines.append("  + Verdict: OK.")

        lang_match = any(p_lang in lang for p_lang in preferred_langs)
        if lang_match:
            score += 10
            feedback_lines.append("  + Used a preferred language.")
        else:
            feedback_lines.append("  o Used a non-preferred language.")

        if prefers_low_time:
            if time_ms < 200:
                score += 10
                feedback_lines.append(f"  + Excellent time ({time_ms}ms), matching preference.")
            elif time_ms < 1000:
                score += 5
                feedback_lines.append(f"  + Good time ({time_ms}ms).")
            else:
                feedback_lines.append(f"  - High time ({time_ms}ms) relative to preference.")
        else:
            feedback_lines.append(f"  o Time: {time_ms}ms.")
        if memory_kb < 65536:
            score += 3
            feedback_lines.append(f"  + Low memory usage ({memory_kb:.0f} KB).")

    else:
        score = 10.0
        feedback_lines.append(f"  - Verdict: {verdict}.")
        if passed_tests > 0:
            score += min(passed_tests * 2, 20)
            feedback_lines.append(f"  - Passed {passed_tests} tests before failing.")
        else:
            feedback_lines.append(f"  - Failed on early tests (passed {passed_tests}).")

        if verdict == "TIME_LIMIT_EXCEEDED" and prefers_low_time:
            score = max(5, score - 5)
            feedback_lines.append(f"  - Failed due to time, conflicting with preference.")
        elif verdict == "MEMORY_LIMIT_EXCEEDED":
            score = max(5, score - 3)
            feedback_lines.append(f"  - Failed due to memory.")


    score = max(0, min(100, score))
    feedback_lines.append(f"----> Fallback Score: {score:.2f}")
    feedback = "\n".join(feedback_lines)

    print(f"  Fallback Evaluation Result: Score={score:.2f}") 
    print("-" * 20) 

    return {"score": score, "feedback": feedback, "full_submission_details": submission_details}

def find_and_evaluate_submission_incremental(
handle: str,
contest_id: int,
problem_index: str,
start_time_unix: int,
end_time_unix: int,
preferred_criteria_str: str
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    print(f"\nChecking & evaluating submissions incrementally for user '{handle}', problem {contest_id}{problem_index}...") # Removed print
# print(f"Preference criteria: '{preferred_criteria_str}'") 
    current_from_index = 1
    checked_count = 0

    try:
        while True:
            params = {
                "handle": handle,
                "from": current_from_index,
                "count": SUBMISSION_BATCH_SIZE
            }
            submissions_batch = _make_api_request("user.status", params)

            if not submissions_batch:
                print(f"  Checked {checked_count} submissions. No more submissions found for user.") 
                break

            checked_count += len(submissions_batch)

            for sub in submissions_batch:
                submission_time = sub.get("creationTimeSeconds")

                if submission_time and submission_time < start_time_unix:
                    print(f"  Reached submission {sub.get('id')} older than start time ({datetime.fromtimestamp(start_time_unix, tz=timezone.utc)}). Stopping search.") # Removed print
                    print(f"  Checked {checked_count} submissions in total.") 
                    return None

                is_correct_problem = (
                    sub.get("problem", {}).get("contestId") == contest_id and
                    sub.get("problem", {}).get("index") == problem_index
                )
                if not is_correct_problem:
                    continue

                is_within_timeframe = (
                    submission_time and
                    start_time_unix <= submission_time <= end_time_unix
                )
                if not is_within_timeframe:
                    continue
                print(f"\n  >>> Found target submission! <<<") 
                print(f"  Checked {checked_count} submissions in total.") 
                print(f"  Submission ID: {sub.get('id')}, Verdict: {sub.get('verdict')}") 
                print(f"  Submission Time (UTC): {datetime.fromtimestamp(submission_time, tz=timezone.utc)}") 
                print("  Proceeding to AI Evaluation...") 
                evaluation_result = evaluate_submission_with_gemini(sub, preferred_criteria_str)
                return sub, evaluation_result

            current_from_index += SUBMISSION_BATCH_SIZE

        # print(f"  No submission found matching criteria for problem {contest_id}{problem_index} within the timeframe.") 
        return None

    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"Error checking submissions incrementally for {handle}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during incremental check: {e}")
        return None

def find_problems_by_criteria(
    tags_str: Optional[str] = None,
    min_rating: Optional[int] = None,
    max_rating: Optional[int] = None,
    n: Optional[int] = None 
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches problems from Codeforces API based on tags and rating range,
    optionally limiting the number of results.

    Args:
        tags_str: A comma-separated string of tags (e.g., "dp,graphs").
        min_rating: Minimum problem rating.
        max_rating: Maximum problem rating.
        n: The maximum number of problems to return. If None, returns all matches.

    Returns:
        A list of problem dictionaries matching the criteria (up to n),
        or None on error.
    """
    print(f"Fetching problems with criteria: tags='{tags_str}', min_rating={min_rating}, max_rating={max_rating}, limit={n}")
    try:
        params = {}
        if tags_str:
            api_tags = ";".join(tag.strip() for tag in tags_str.split(',') if tag.strip())
            if api_tags:
                params["tags"] = api_tags

        problemset_data = _make_api_request("problemset.problems", params)

        if problemset_data is None:
             print(" Failed: No data received from problemset.problems API call.")
             return None

        problems = []
        if isinstance(problemset_data, dict):
            problems = problemset_data.get("problems", [])
        else:
            print(f" Warning: Unexpected API response format (expected dict, got {type(problemset_data)}).")
            return None

        # Filter by rating client-side
        filtered_problems = []
        for p in problems:
            problem_rating = p.get("rating")
            passes_rating_filter = True
            if problem_rating is not None:
                if min_rating is not None and problem_rating < min_rating:
                    passes_rating_filter = False
                if max_rating is not None and problem_rating > max_rating:
                    passes_rating_filter = False
            elif min_rating is not None or max_rating is not None:
                 passes_rating_filter = False

            if passes_rating_filter:
                filtered_problems.append(p)

        print(f"  Found {len(problems)} problems initially, {len(filtered_problems)} after rating filter.")

        if n is not None and n > 0:
            limited_problems = filtered_problems[:n] 
            print(f"  Limiting results to {len(limited_problems)} based on request for {n}.")
            return limited_problems
        else:
            # Return all filtered problems if n is not specified or invalid
            return filtered_problems

    except Exception as e:
        print(f"An unexpected error occurred while finding problems: {e}")
        import traceback
        traceback.print_exc()
        return None

logger = logging.getLogger(__name__)

def fetch_problem_metadata_cf(contest_id: int, problem_index: str) -> dict | None:
    """
    Fetches metadata (title, tags, rating) for a specific Codeforces problem.

    Uses the 'problemset.problems' API endpoint.

    WARNING: This implementation currently fetches ALL problems from the API
             and filters locally because there isn't a direct CF API endpoint
             for a single problem by ID/index. This is VERY INEFFICIENT.
             Implementing a local cache/database of problems fetched periodically
             is STRONGLY RECOMMENDED for better performance.

    Args:
        contest_id: The contest ID of the problem.
        problem_index: The index of the problem (e.g., 'A', 'B1').

    Returns:
        A dictionary containing {'title': str, 'tags': str, 'rating': int}
        if the problem is found, otherwise None. Returns None on API errors.
        Keys will be present even if values are None from the API.
    """
    logger.info(f"Attempting to fetch metadata for Codeforces problem {contest_id}{problem_index}")

    try:
        problemset_data = _make_api_request("problemset.problems")
        if not isinstance(problemset_data, dict) or "problems" not in problemset_data:
            logger.error(f"Invalid or unexpected response structure received from problemset.problems API. "
                         f"Expected dict with 'problems' key, got: {type(problemset_data)}")
            return None

        problems = problemset_data.get("problems", [])
        if not isinstance(problems, list):
             logger.error(f"Invalid 'problems' data type in response. Expected list, got: {type(problems)}")
             return None

        found_problem = None
        for problem in problems:
            if not isinstance(problem, dict):
                logger.warning(f"Skipping invalid item in problems list (not a dict): {problem}")
                continue

            p_contest_id = problem.get("contestId")
            p_index = problem.get("index")

            if isinstance(p_contest_id, int) and isinstance(p_index, str) and \
               p_contest_id == contest_id and p_index == problem_index:
                found_problem = problem
                break 

        if found_problem:
            title = found_problem.get("name")
            tags_list = found_problem.get("tags", [])
            rating = found_problem.get("rating")

            tags_str = ", ".join(str(tag) for tag in tags_list if tag) 

            metadata = {
                "title": title if isinstance(title, str) else None,
                "tags": tags_str, 
                "rating": rating if isinstance(rating, int) else None,
            }
            logger.info(f"Successfully found metadata for {contest_id}{problem_index}: "
                        f"Title='{metadata['title']}', Rating={metadata['rating']}, Tags='{metadata['tags']}'")
            return metadata
        else:
            # If loop completes without finding the problem
            logger.warning(f"Problem {contest_id}{problem_index} not found in the fetched problem set.")
            return None 

    except requests.exceptions.RequestException as e:
         logger.error(f"Network error fetching metadata for {contest_id}{problem_index}: {e}", exc_info=True)
         return None
    except ValueError as e: 
         logger.error(f"API or data processing error for {contest_id}{problem_index}: {e}", exc_info=True)
         return None
    except Exception as e:
        logger.error(f"Unexpected error fetching metadata for {contest_id}{problem_index}: {e}", exc_info=True)
        return None