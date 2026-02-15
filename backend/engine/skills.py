# engine/skills.py
import re
from spacy.tokens import Doc

_SOFT_SKILLS = {
    "communication", "leadership", "teamwork", "problem solving",
    "critical thinking", "time management", "adaptability", "creativity",
    "collaboration", "attention to detail", "analytical thinking",
    "decision making", "conflict resolution", "negotiation", "presentation",
    "mentoring", "coaching", "strategic thinking", "stakeholder management",
    "cross-functional", "client management", "vendor management",
    "self-motivated", "detail-oriented", "fast learner", "multitasking",
    # Phrase variants
    "requirements management", "project management", "change management",
    "risk management", "team coordination", "cross functional",
    "communication skills", "excellent communication", "strong communication",
    "technical documentation", "reporting",
}

_NOISE = {
    "experience", "years", "team", "project", "ability", "skills",
    "job", "candidate", "work", "role", "position", "company",
    "please", "required", "preferred", "must", "will", "using",
    "description", "responsibilities", "duties", "following",
}


def extract_soft_skills(text: str) -> set:
    text_low = text.lower()
    found = set()
    for skill in _SOFT_SKILLS:
        if skill in text_low:
            found.add(skill)
    return found


def spacy_extract_skills(doc: Doc) -> set:
    text_low = doc.text.lower()
    found = set()
    for chunk in doc.noun_chunks:
        term = chunk.text.lower().strip()
        if 1 < len(term.split()) <= 4 and term not in _NOISE:
            if any(c.isalpha() for c in term):
                found.add(term)
    for token in doc:
        if token.pos_ in ("PROPN", "NOUN") and len(token.text) > 2:
            term = token.text.lower()
            if term not in _NOISE and term.isalpha():
                found.add(term)
    return found


def keyword_frequency(text: str, skills: list) -> dict:
    text_low = text.lower()
    return {
        skill: len(re.findall(rf"\b{re.escape(skill.lower())}\b", text_low))
        for skill in skills
    }


def detect_keyword_stuffing(resume_text: str, skills: list, threshold: int = 6) -> list:
    """
    Detect keyword stuffing, but exclude primary job skills.
    Primary skills are determined by high frequency across the JD skill list.
    
    FIXED: Even primary skills get flagged if they appear EXTREMELY frequently (>12)
    This prevents "design" appearing 17x from being marked as acceptable.
    """
    word_count = len(resume_text.split())
    adjusted_threshold = max(threshold, word_count // 120)
    
    freq = keyword_frequency(resume_text, skills)
    
    # Identify primary skills (top 3 most central to the role)
    # These are skills that appear most frequently in the skill list itself
    primary_skills = set()
    if len(skills) > 0:
        skill_mentions = {}
        for skill in skills:
            # How many other skills contain this skill?
            skill_mentions[skill] = sum(1 for s in skills if skill.lower() in s.lower())
        
        # Top 3 most central skills
        sorted_skills = sorted(skill_mentions.items(), key=lambda x: x[1], reverse=True)
        primary_skills = {s[0] for s in sorted_skills[:3]}
    
    # Flag stuffing based on two conditions:
    # 1. NOT a primary skill AND count >= threshold
    # 2. IS a primary skill BUT count is EXTREMELY high (>12)
    stuffed = []
    for skill, count in freq.items():
        if count >= adjusted_threshold:
            # If it's not a primary skill, flag it
            if skill not in primary_skills:
                stuffed.append(skill)
            # If it IS a primary skill but appears >12 times, still flag it
            elif count > 12:
                stuffed.append(skill)
    
    return stuffed
