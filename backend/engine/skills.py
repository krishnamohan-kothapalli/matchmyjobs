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
    # Generic work terms
    "experience", "years", "team", "project", "ability", "skills",
    "job", "candidate", "work", "role", "position", "company",
    "please", "required", "preferred", "must", "will", "using",
    "description", "responsibilities", "duties", "following",
    
    # Common filler words
    "strong", "excellent", "good", "knowledge", "understanding",
    "working", "proven", "demonstrated", "successful", "effective",
    
    # Time and quantity terms
    "time", "year", "month", "day", "week", "number", "level",
    "multiple", "various", "several", "many", "other", "additional",
    
    # Business generic terms
    "business", "client", "customer", "stakeholder", "partner",
    "vendor", "product", "service", "solution", "platform",
    "process", "system", "tool", "application", "environment",
    
    # Action/descriptor words
    "develop", "implement", "manage", "create", "build",
    "design", "support", "maintain", "ensure", "provide",
    
    # Organizational terms
    "department", "organization", "division", "unit", "group",
    "sector", "industry", "field", "area", "domain",
    
    # Common adjectives
    "new", "current", "existing", "future", "potential", "possible",
    "available", "necessary", "important", "critical", "key",
    
    # Vague skill descriptors
    "technical", "professional", "operational", "strategic",
    "tactical", "functional", "cross-functional", "cross functional",
}


def extract_soft_skills(text: str) -> set:
    text_low = text.lower()
    found = set()
    for skill in _SOFT_SKILLS:
        if skill in text_low:
            found.add(skill)
    return found


def spacy_extract_skills(doc: Doc) -> set:
    """
    Extract skills using spaCy NLP with improved filtering.
    
    ENHANCED v3.1: 
    - Better noise filtering
    - Minimum word length requirements  
    - Exclude pure adjectives/verbs
    - Require at least one noun or proper noun in phrase
    """
    text_low = doc.text.lower()
    found = set()
    
    # Extract from noun chunks (phrases)
    for chunk in doc.noun_chunks:
        term = chunk.text.lower().strip()
        
        # Skip if too short or too long
        words = term.split()
        if not (2 <= len(words) <= 4):
            continue
            
        # Skip if in noise list or contains noise words
        if term in _NOISE or any(word in _NOISE for word in words):
            continue
        
        # Must have alphabetic characters
        if not any(c.isalpha() for c in term):
            continue
            
        # Must have at least one significant word (not all adjectives)
        has_noun = any(token.pos_ in ("NOUN", "PROPN") for token in chunk)
        if not has_noun:
            continue
            
        # Add if it looks like a real skill
        found.add(term)
    
    # Known technical terms that might be missed
    _TECH_TERMS = {
        "python", "java", "javascript", "typescript", "sql", "nosql",
        "aws", "azure", "gcp", "docker", "kubernetes", "jenkins",
        "react", "angular", "vue", "node", "express", "django",
        "flask", "spring", "hibernate", "tensorflow", "pytorch",
        "git", "jira", "agile", "scrum", "devops", "ci/cd",
        "html", "css", "sass", "rest", "graphql", "api",
        "mongodb", "postgresql", "mysql", "redis", "elasticsearch",
    }
    
    # Extract standalone proper nouns and specific nouns
    for token in doc:
        if token.pos_ in ("PROPN", "NOUN") and len(token.text) > 2:
            term = token.text.lower()
            
            # Skip noise
            if term in _NOISE:
                continue
                
            # Must be alphanumeric
            if not any(c.isalnum() for c in term):
                continue
            
            # Add if it's a known tech term or looks like one
            if (term in _TECH_TERMS or
                token.text[0].isupper() or 
                any(c.isdigit() for c in term)):
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
