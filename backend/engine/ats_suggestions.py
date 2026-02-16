# engine/ats_suggestions.py
# ═══════════════════════════════════════════════════════════════════════════════
# Industry-Aligned ATS Suggestions
#
# Generates specific, actionable suggestions based on how real ATS systems work.
# Each suggestion references specific ATS behaviors and includes:
# - Which ATS system(s) this affects
# - Exact impact on score
# - Copy-paste ready fixes
# ═══════════════════════════════════════════════════════════════════════════════

from typing import List, Dict


def generate_ats_suggestions(
    ats_score_breakdown: Dict,
    extraction: Dict,
    final_score: float
) -> List[Dict]:
    """
    Generate priority-ranked suggestions based on ATS scoring gaps.
    
    Strategy:
    1. Fix critical gates first (education, keyword match <40%)
    2. Fix high-impact improvements (placement, experience)
    3. Polish formatting and optimization
    
    Returns max 5 suggestions in priority order.
    """
    suggestions = []
    breakdown = ats_score_breakdown["breakdown"]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CRITICAL: Education Gate (Auto-reject if fails)
    # ═══════════════════════════════════════════════════════════════════════════
    
    if breakdown["education"]["score"] == 0:
        required = breakdown["education"]["required"]
        suggestions.append({
            "priority": "critical",
            "category": "hard_gate",
            "ats_systems": ["Workday", "iCIMS", "Taleo"],
            "area": "Education Section",
            "issue": f"JD requires {required} degree but none detected",
            "fix": f"Add Education section with: '{required.title()} of [Your Field], [University Name], [Graduation Year]'. Place this section after Experience.",
            "why_it_matters": f"Workday and iCIMS use education as a HARD GATE. If required={required} and you don't have it in your resume, you're AUTO-REJECTED before any human sees your application.",
            "score_impact": "+10 points (passes critical gate)",
            "implementation": "Add between Experience and Skills sections:\n\nEDUCATION\nBachelor of Science in Computer Science\nUniversity of California, Berkeley\nGraduated: May 2018"
        })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CRITICAL: Keyword Match <40% (Workday auto-reject threshold)
    # ═══════════════════════════════════════════════════════════════════════════
    
    keyword_match = breakdown["keyword_match"]
    if keyword_match["match_rate"] < 40:
        missing_skills = extraction.get("missing_skills", [])[:5]
        suggestions.append({
            "priority": "critical",
            "category": "keyword_match",
            "ats_systems": ["Workday", "Greenhouse", "Taleo"],
            "area": "Skills Coverage",
            "issue": f"Only {keyword_match['match_rate']}% of required skills match (need 40%+ minimum)",
            "fix": f"Add these missing skills: {', '.join(missing_skills)}. Add them to your Skills section AND weave into 2-3 experience bullets showing how you used them.",
            "why_it_matters": f"Workday auto-rejects candidates below 40% keyword match. You're at {keyword_match['match_rate']}% = automatic rejection. Taleo ranks purely by keyword count - missing skills = invisible to recruiters.",
            "score_impact": "+10-20 points (moves from auto-reject to qualified tier)",
            "implementation": f"Skills Section - Add:\n{', '.join(missing_skills)}\n\nExperience Section - Rewrite a bullet:\n'Developed features using {missing_skills[0] if missing_skills else 'required-skill'}, improving system performance by 30%'"
        })
    
    elif keyword_match["match_rate"] < 60:
        missing_skills = extraction.get("missing_skills", [])[:3]
        suggestions.append({
            "priority": "high",
            "category": "keyword_match",
            "ats_systems": ["Workday", "Greenhouse"],
            "area": "Skills Coverage",
            "issue": f"{keyword_match['match_rate']}% match - need 60%+ to be 'Qualified' in Workday",
            "fix": f"Add {len(missing_skills)} missing critical skills: {', '.join(missing_skills)}",
            "why_it_matters": "Workday has 3 tiers: 80%+=Highly Qualified, 60-79%=Qualified, 40-59%=Potentially Qualified. You're in the bottom tier. Moving to 60%+ bumps you up significantly.",
            "score_impact": "+5-10 points (tier upgrade in Workday)",
            "implementation": f"Add to Skills section: {', '.join(missing_skills)}\nMention in Professional Summary: 'Experienced in {missing_skills[0] if missing_skills else 'key-skill'}...'"
        })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HIGH PRIORITY: Keyword Placement (Greenhouse ranking)
    # ═══════════════════════════════════════════════════════════════════════════
    
    placement = breakdown["keyword_placement"]
    if placement["score"] < 15:  # Less than 15/25 points
        matched_skills = extraction.get("matched_skills", [])[:3]
        
        if placement["summary_hits"] < 2:
            suggestions.append({
                "priority": "high",
                "category": "keyword_placement",
                "ats_systems": ["Greenhouse", "Lever", "SmartRecruiters"],
                "area": "Professional Summary",
                "issue": f"Only {placement['summary_hits']} keywords in your Summary (need 3+)",
                "fix": f"Rewrite your Professional Summary to include: {', '.join(matched_skills)}. Example: 'Senior Engineer with 5+ years expertise in {matched_skills[0] if matched_skills else 'Python'}, {matched_skills[1] if len(matched_skills) > 1 else 'AWS'}, and {matched_skills[2] if len(matched_skills) > 2 else 'Docker'}, delivering scalable solutions...'",
                "why_it_matters": "Greenhouse weights Summary keywords 5X higher than Skills lists. Your Summary is the FIRST thing recruiters and ATS systems read. No keywords there = ranked lower than identical candidates who optimize this.",
                "score_impact": "+8-12 points (significant Greenhouse ranking boost)",
                "implementation": "PROFESSIONAL SUMMARY\nSenior Software Engineer with 6+ years building scalable applications using Python, AWS, and Docker. Proven track record of [achievement]..."
            })
        
        elif placement["experience_hits"] < 4:
            suggestions.append({
                "priority": "high",
                "category": "keyword_placement",
                "ats_systems": ["Greenhouse", "Lever"],
                "area": "Experience Bullets",
                "issue": f"Only {placement['experience_hits']} keywords in Experience section (need 5+)",
                "fix": f"Rewrite 3-4 experience bullets to include {', '.join(matched_skills[:2])}. Don't just list them - show USAGE. Example: 'Built API using {matched_skills[0] if matched_skills else 'Python'} that processed 10K requests/day'",
                "why_it_matters": "Greenhouse weights Experience keywords 3X higher than Skills. Keywords in bullets = proof you actually used the technology. Keywords only in Skills = just claims.",
                "score_impact": "+5-8 points (Greenhouse ranking improvement)",
                "implementation": "Experience bullets - Rewrite to include skills:\n• Built REST API using Python and Flask, handling 10K+ daily requests\n• Deployed infrastructure on AWS using Docker and Kubernetes\n• Implemented CI/CD pipeline with Jenkins, reducing deploy time by 40%"
            })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HIGH PRIORITY: Experience Gap
    # ═══════════════════════════════════════════════════════════════════════════
    
    experience = breakdown["experience"]
    if experience["score"] < 10:  # Significant gap
        gap = experience.get("gap", 0)
        suggestions.append({
            "priority": "high",
            "category": "experience",
            "ats_systems": ["Workday", "iCIMS"],
            "area": "Experience Timeline",
            "issue": f"You have {experience['years_detected']} years but JD requires {experience['years_required']} ({gap} year gap)",
            "fix": "1) Verify your date ranges are correct and visible (format: 'Jan 2020 - Present'). 2) Include ALL relevant experience (internships, freelance, side projects count). 3) If gap is real, emphasize DEPTH of experience: 'Led team of 5', 'Managed $2M budget', 'Owned critical infrastructure'",
            "why_it_matters": "Workday calculates experience from your date ranges. Short by 2+ years = likely auto-filtered. Close gap (within 1 year) = recruiter may overlook if skills are strong.",
            "score_impact": f"+5-10 points (reduces experience penalty)",
            "implementation": "Verify each job has:\nSoftware Engineer | Google\nJan 2020 - Present (3 years)\n\nInclude side projects:\nFreelance Developer | Self-Employed\nJan 2018 - Dec 2019 (2 years)"
        })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MEDIUM PRIORITY: Formatting Issues
    # ═══════════════════════════════════════════════════════════════════════════
    
    formatting = breakdown["formatting"]
    if formatting["score"] < 7:
        issues = formatting.get("issues", [])
        suggestions.append({
            "priority": "medium",
            "category": "formatting",
            "ats_systems": ["iCIMS", "Taleo"],
            "area": "Document Structure",
            "issue": f"Formatting issues detected: {', '.join(issues[:2])}",
            "fix": "1) Use standard section headings: PROFESSIONAL EXPERIENCE, EDUCATION, SKILLS (all caps or title case). 2) Include phone number and email at top. 3) Add 3-5 quantified achievements with numbers (%, $, team size).",
            "why_it_matters": "iCIMS and Taleo have WEAK parsers. Non-standard format = data extraction fails = your info doesn't populate in recruiter's system = looks like an empty resume. Simple format = clean parsing.",
            "score_impact": "+3-5 points (ensures data is actually read)",
            "implementation": "Use this structure:\n[Name]\n[Email] | [Phone] | [LinkedIn]\n\nPROFESSIONAL SUMMARY\n[2-3 sentences]\n\nPROFESSIONAL EXPERIENCE\n[Job title] | [Company]\n[Dates]\n• [Bullet with metric]\n\nEDUCATION\n[Degree] | [School]\n\nSKILLS\n[List]"
        })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MEDIUM PRIORITY: Metrics/Impact
    # ═══════════════════════════════════════════════════════════════════════════
    
    if formatting.get("metrics_found", 0) < 3:
        suggestions.append({
            "priority": "medium",
            "category": "impact",
            "ats_systems": ["Workday", "Greenhouse", "SmartRecruiters"],
            "area": "Quantified Achievements",
            "issue": f"Only {formatting.get('metrics_found', 0)} quantified results (need 5+)",
            "fix": "Add numbers to 5 bullets. Formula: [Action Verb] + [What] + [How/Tool] + [Measurable Result]. Examples:\n• Improved API latency by 40% using Redis caching\n• Led team of 8 engineers delivering $2M project\n• Reduced deployment time from 2 hours to 15 minutes\n• Increased test coverage from 60% to 95%",
            "why_it_matters": "Workday's AI scoring heavily weights quantified achievements. Studies show resumes with metrics are ranked 2-3 positions higher than identical candidates without them. Numbers = credibility.",
            "score_impact": "+2-5 points (AI scoring boost across all systems)",
            "implementation": "Rewrite bullets to include:\n• Performance improvements: 'Reduced load time by X%'\n• Scale: 'Handled X requests/day', 'Served X users'\n• Team: 'Led team of X', 'Collaborated with X teams'\n• Money: 'Saved $X', 'Generated $X revenue'\n• Time: 'Reduced from X to Y', 'Delivered X weeks early'"
        })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Sort by priority and return top 5
    # ═══════════════════════════════════════════════════════════════════════════
    
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    suggestions.sort(key=lambda x: priority_order.get(x["priority"], 3))
    
    return suggestions[:5]


def generate_fallback_suggestions(final_score: float) -> List[Dict]:
    """
    Fallback suggestions when detailed analysis unavailable.
    Still ATS-aligned but generic.
    """
    return [
        {
            "priority": "high",
            "category": "keyword_match",
            "ats_systems": ["All ATS"],
            "area": "Skills & Keywords",
            "issue": "Resume may not match job requirements closely enough",
            "fix": "Mirror the EXACT language from the job description. If they say 'project management', use 'project management' (not 'managed projects'). Use their terminology word-for-word.",
            "why_it_matters": "Most ATS systems do literal keyword matching. Synonyms don't count. Exact phrase matching is critical.",
            "score_impact": "+10-15 points",
            "implementation": "Compare JD to resume side-by-side. Copy key phrases into your Experience and Summary."
        },
        {
            "priority": "high",
            "category": "keyword_placement",
            "ats_systems": ["Greenhouse", "Lever"],
            "area": "Professional Summary",
            "issue": "Keywords likely only in Skills section",
            "fix": "Add 3-5 critical skills to your Professional Summary. Make it keyword-rich but natural: 'Senior [Title] with expertise in [skill 1], [skill 2], and [skill 3]...'",
            "why_it_matters": "Summary keywords are weighted 5X higher than Skills lists in Greenhouse and Lever.",
            "score_impact": "+8-12 points",
            "implementation": "Rewrite first 2-3 sentences of resume to include main technologies."
        },
        {
            "priority": "medium",
            "category": "impact",
            "ats_systems": ["All ATS"],
            "area": "Experience Bullets",
            "issue": "Likely missing quantified achievements",
            "fix": "Add numbers to 5+ bullets: percentages, dollar amounts, time saved, team size, users served. Example: 'Improved performance by 40%' instead of 'Improved performance'.",
            "why_it_matters": "Workday's AI gives higher scores to resumes with metrics. Recruiters spend 2X longer on resumes with numbers.",
            "score_impact": "+5-8 points",
            "implementation": "Audit each bullet point. Add: X%, $X, X users, X months, team of X, etc."
        }
    ]
