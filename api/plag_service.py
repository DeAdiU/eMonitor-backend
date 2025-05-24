import logging
from .models import AssessmentSubmission
try:
    from .plagcheck import plagchecker
    PLAGCHECK_AVAILABLE = True
except ImportError:
    PLAGCHECK_AVAILABLE = False
    def plagchecker(code1, code2, language): return 0.0 

logger = logging.getLogger(__name__)

def calculate_max_plagiarism(current_submission: AssessmentSubmission) -> int | None:
    """
    Calculates the maximum plagiarism score against other submissions for the same question.

    Args:
        current_submission: The AssessmentSubmission object containing the newly scraped code.

    Returns:
        The maximum plagiarism score (0-100 integer), or None if checks cannot be performed.
    """
    if not PLAGCHECK_AVAILABLE:
        logger.warning("Plagiarism checker unavailable, skipping check.")
        return None

    current_code = current_submission.submitted_code
    current_lang_raw = getattr(current_submission, 'language', '').lower() 

    # Map scraped language to plagchecker language ('python', 'cpp', 'java')
    current_lang = None
    if 'python' in current_lang_raw or 'py' in current_lang_raw: current_lang = 'python'
    elif 'c++' in current_lang_raw or 'cpp' in current_lang_raw or 'gcc' in current_lang_raw: current_lang = 'cpp'
    elif 'java' in current_lang_raw: current_lang = 'java'

    if not current_code or not current_lang:
        logger.warning(f"Cannot perform plagiarism check for Sub PK {current_submission.pk}: Missing code or unsupported language ('{current_lang_raw}').")
        return None

    logger.info(f"Performing plagiarism check for PK: {current_submission.pk} (Lang: {current_lang})")
    other_submissions = AssessmentSubmission.objects.filter(
        question=current_submission.question,
        assessment=current_submission.assessment
    ).exclude(pk=current_submission.pk).select_related('student') 

    if not other_submissions:
        logger.info("No other submissions found for plagiarism comparison.")
        return 0 

    max_plag_score = 0.0
    logger.info(f"Comparing against {other_submissions.count()} other submission(s).")
    for other_sub in other_submissions:
        if other_sub.submitted_code:
            try:
                score = plagchecker(current_code, other_sub.submitted_code, current_lang)
                if score > max_plag_score:
                    max_plag_score = score
                logger.debug(f"  Compared with {other_sub.student.username} (Sub PK: {other_sub.pk}), Score: {score:.4f}")
            except Exception as plag_err:
                logger.error(f"Error running plagchecker between {current_submission.pk} and {other_sub.pk}: {plag_err}", exc_info=True)

    logger.info(f"Max plagiarism score found: {max_plag_score:.4f}")
    return int(max_plag_score * 100)