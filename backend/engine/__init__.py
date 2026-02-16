import spacy
import os
from . import density

# ---------------------------------------------------------------------------
# Load spaCy model once at package import — all submodules share this instance
# ---------------------------------------------------------------------------

def _load_nlp():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        os.system("python -m spacy download en_core_web_sm")
        return spacy.load("en_core_web_sm")


nlp = _load_nlp()

# Inject the shared nlp instance into the density module
density.nlp = nlp

# Public surface
from .scorer import run_analysis

__all__ = ["nlp", "run_analysis"]
