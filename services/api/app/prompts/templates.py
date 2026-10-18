from typing import Dict
import os

# Versioned prompt templates
# Each template includes few-shot examples as per requirements
PROMPTS = {
    "question_answer": {
        "template": "Answer the user's question using only the relevant text below. Respond in plain everyday language in 1-3 short sentences. Preserve exact names, dates, amounts, and conditions from the text. If the text does not answer the question, say that clearly. Do not guess, add legal conclusions, or give legal advice.\n\nUser's question: {question}\n\nRelevant document text:\n{text}\n\nAnswer:",
        "system": "You are a careful legal-document assistant. Give one direct, concise, text-grounded answer. Do not repeat the question or add headings.",
    },
    "classify_label": {
        "template": "Classify the following document into one of these categories: [rental, employment, legal_notice, service_agreement, non_legal].\n\nDocument text: {text}\n\nCategory:",
        "system": "You are a document classifier. Only output the category label.",
        "few_shot": [
            {"input": "This lease agreement is between...", "output": "rental"},
            {"input": "I am writing to notify you that your employment...", "output": "employment"},
            {"input": "The weather is nice today.", "output": "non_legal"}
        ]
    }
}

def get_prompt(key: str, **kwargs) -> str:
    template = PROMPTS.get(key, {}).get("template", "")
    return template.format(**kwargs)

def get_system_prompt(key: str) -> str:
    return PROMPTS.get(key, {}).get("system", "")
