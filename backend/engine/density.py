from collections import Counter
import spacy

nlp = None  # injected by __init__.py to avoid double-loading


def calculate_density(res_text: str, jd_text: str, top_n: int = 5) -> dict:
    """
    Compare keyword frequency between the resume and the JD.
    Returns labels + counts for both sides, used by the bar chart on audit.html.
    """
    jd_doc  = nlp(jd_text)
    res_doc = nlp(res_text)

    # Top N meaningful words from the JD (no stopwords, alpha, length > 3)
    jd_words = [
        t.text.lower()
        for t in jd_doc
        if not t.is_stop and t.is_alpha and len(t.text) > 3
    ]
    top_jd = Counter(jd_words).most_common(top_n)

    # How often those same words appear in the resume
    res_counts = Counter(
        t.text.lower() for t in res_doc if t.is_alpha
    )

    return {
        "labels":      [word for word, _ in top_jd],
        "jd_counts":   [count for _, count in top_jd],
        "res_counts":  [res_counts.get(word, 0) for word, _ in top_jd],
        "explanation": (
            "High density in core keywords signals Subject Matter Expertise to the ATS. "
            "If your resume counts are low compared to the JD, the algorithm may rank "
            "you as a secondary match."
        ),
    }
