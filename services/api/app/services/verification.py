import re
from typing import List, Tuple, Dict
from services.api.app.orchestrator.state import AnalysisResult

class VerificationService:
    """Ensures AI claims are grounded in the actual document text."""

    def verify_claim(self, claim: str, context: str) -> Tuple[bool, List[str]]:
        """
        Checks if a claim is supported by the provided context.
        In a production system, this would use a Natural Language Inference (NLI) model
        or a specific 'judge' LLM prompt. For now, we use a high-precision keyword-based
        overlap check combined with sentence extraction.
        """
        if not context or not claim:
            return False, []

        # Split context into sentences
        sentences = re.split(r'(?<!\bRs\.)(?<!\bNo\.)(?<!\bMr\.)(?<!\bDr\.)(?<=[.!?])\s+', context)
        evidence = []

        # Simple heuristic: find sentences that share a significant number of keywords
        claim_words = set(re.findall(r'\w+', claim.lower()))
        # Remove common stop words for better precision
        stop_words = {"the", "a", "an", "is", "are", "and", "or", "of", "in", "to"}
        keywords = claim_words - stop_words

        for sent in sentences:
            sent_words = set(re.findall(r'\w+', sent.lower()))
            overlap = keywords.intersection(sent_words)
            # If more than 30% of keywords match, we treat it as evidence for this MVP
            if len(keywords) > 0 and (len(overlap) / len(keywords)) > 0.3:
                evidence.append(sent.strip())

        is_grounded = len(evidence) > 0
        return is_grounded, evidence

verification_service = VerificationService()
