# evaluation_service.py
import logging
from .models import AssessmentSubmission, Assessment # Assuming models are in the same app
try:
    # Assuming you saved the evaluation code as evaluation_module.py
    from .codeforces import evaluate_submission_with_gemini, evaluate_submission_fallback
    EVALUATION_AVAILABLE = True
except ImportError:
    EVALUATION_AVAILABLE = False
    # Dummy functions
    def evaluate_submission_with_gemini(details, criteria): return {"score": 0.0, "feedback": "Evaluation module unavailable.", "full_submission_details": details}
    def evaluate_submission_fallback(details, criteria): return {"score": 0.0, "feedback": "Evaluation module unavailable.", "full_submission_details": details}

logger = logging.getLogger(__name__)

def evaluate_submission(submission: AssessmentSubmission, assessment: Assessment) -> dict:
    """
    Prepares submission data and calls the appropriate evaluation function.

    Args:
        submission: The AssessmentSubmission object with scraped data.
        assessment: The Assessment object for preferred criteria.

    Returns:
        A dictionary containing {'score': float, 'feedback': str}.
    """
    logger.info(f"Performing evaluation for PK: {submission.pk}")

    # Prepare details dict for evaluation function, mimicking Codeforces structure where helpful
    eval_details = {
        "id": submission.codeforces_submission_id,
        "contestId": submission.question.contest_id,
        "problem": {
            "contestId": submission.question.contest_id,
            "index": submission.question.problem_index,
            "name": submission.question.title,
            "rating": submission.question.rating,
            "tags": submission.question.tags.split(',') if submission.question.tags else []
        },
        "author": {"members": [{"handle": submission.student.username}]},
        "programmingLanguage": getattr(submission, 'language', 'Unknown'),
        "verdict": submission.verdict or 'UNKNOWN', 
        "passedTestCount": submission.passed_test_count if submission.passed_test_count is not None else 0,
        "timeConsumedMillis": submission.time_consumed_millis,
        "memoryConsumedBytes": submission.memory_consumed_bytes,
        "plagiarismVerdict": submission.plagiarism_score or 'UNKNOWN',
        # "sourceCode": submission.submitted_code
    }

    preferred_criteria = assessment.preferred_criteria or "Focus on correctness (AC verdict) and efficiency (low time/memory). Prefer C++ or Python or Java."

    if EVALUATION_AVAILABLE:
         evaluation_result = evaluate_submission_with_gemini(eval_details, preferred_criteria)
    else:
         logger.warning("Evaluation module unavailable, using fallback directly.")
         evaluation_result = evaluate_submission_fallback(eval_details, preferred_criteria)

    score = evaluation_result.get('score', 0.0)
    feedback = evaluation_result.get('feedback', 'Evaluation failed to produce feedback.')

    logger.info(f"Evaluation completed for PK: {submission.pk}. Score: {score}")
    return {"score": score, "feedback": feedback}