import re
from typing import Tuple

ESCALATION_MESSAGE = (
    "I can't decide whether this document or a clause is legal, valid or enforceable, or tell you what to do. "
    "That is a legal conclusion that depends on your jurisdiction and facts outside the document. "
    "I can explain what a specific clause says in plain language and point to the exact text. "
    "For a decision, please consult a qualified lawyer; in India, your District Legal Services Authority "
    "can help you find free legal aid."
)


def silent_message(missing_words) -> str:
    words = ", ".join(f"\u201c{w}\u201d" for w in missing_words)
    return (
        f"I couldn't find anything in this document about {words}. The document appears to be silent on "
        "this, so I won't guess. It may use different wording; try rephrasing, or ask about a specific clause. "
        "If this matters to you, a qualified lawyer can tell you what applies when a contract says nothing."
    )

_VERDICT_QUESTION = re.compile(
    r"\b("
    r"(is|are|was) (this|it|that|the \w+|these|clause \w+)( \w+){0,3} (legal|illegal|valid|invalid|enforceable|binding|lawful|unlawful)"
    r"|enforceab\w*|legally (valid|binding)"
    r"|should i (sign|accept|agree|refuse|sue)"
    r"|(will|would|can|could) i (win|sue|lose)"
    r"|take (them|him|her|my \w+) to court"
    r"|is it (worth|safe) (signing|to sign)"
    r")\b",
    re.IGNORECASE,
)


class SafetyService:
    """Enforces non-negotiable legal constraints."""

    def check_question(self, question: str) -> Tuple[bool, str]:
        """Detects verdict-seeking questions before any model call.

        Returns (needs_escalation, reason).
        """
        match = _VERDICT_QUESTION.search(question or "")
        if match:
            return True, "verdict_request"
        return False, ""

    def validate_response(self, response: str) -> Tuple[bool, str]:
        """
        Checks if the response contains forbidden legal verdicts.
        Returns (is_safe, error_message).
        """
        forbidden_terms = [
            "enforceable", "illegal", "you will win", "should sign",
            "legal advice", "binding", "lawsuit", "court will"
        ]

        for term in forbidden_terms:
            if term.lower() in response.lower():
                return False, f"Response contains forbidden legal verdict: '{term}'"

        return True, ""


safety_service = SafetyService()
