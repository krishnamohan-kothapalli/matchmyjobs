// ============================================================
// MatchMyJobs v3.0 - Enhanced Results Renderer
// ============================================================

// ── Constants ──────────────────────────────────────────────
const SCORE_THRESHOLDS = {
  HIGH: 80,
  MODERATE: 55,
  LOW: 0
};

const SCORE_LEVELS = [
  { min: SCORE_THRESHOLDS.HIGH,     label: "HIGH MATCH",     color: "var(--green-500)" },
  { min: SCORE_THRESHOLDS.MODERATE, label: "MODERATE MATCH", color: "var(--yellow-500)" },
  { min: SCORE_THRESHOLDS.LOW,      label: "WEAK MATCH",     color: "var(--red-500)" },
];

const SCORE_MESSAGES = [
  { min: 80, text: "Expert alignment. Your profile is in the top 5% for this job description." },
  { min: 55, text: "Strong potential. Address the gaps below to bypass automated filters." },
  { min:  0, text: "Significant gaps detected. Major keyword optimization required for ATS visibility." },
];

const SCORE_COLORS = {
  EXCELLENT: { threshold: 70, color: "var(--green-500)" },
  GOOD:      { threshold: 40, color: "var(--yellow-500)" },
  POOR:      { threshold: 0,  color: "var(--red-500)" }
};

// ── Analytics ──────────────────────────────────────────────
function trackEvent(eventName, props = {}) {
  if (window.plausible) {
    window.plausible(eventName, { props });
  }
  
  if (window.location.hostname === 'localhost') {
    console.log('[Analytics]', eventName, props);
  }
}

// ── Sanitization ───────────────────────────────────────────
function sanitizeHTML(str) {
  if (!str) return '';
  
  // Use DOMPurify if available, otherwise fallback to basic sanitization
  if (window.DOMPurify) {
    return DOMPurify.sanitize(str, {
      ALLOWED_TAGS: ['strong', 'em', 'br', 'p', 'span'],
      ALLOWED_ATTR: []
    });
  }
  
  // Fallback: basic text encoding
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Helpers ────────────────────────────────────────────────
function getLevel(score, levels) {
  return levels.find(l => score >= l.min) || levels[levels.length - 1];
}

function getScoreColor(percentage) {
  if (percentage >= SCORE_COLORS.EXCELLENT.threshold) return SCORE_COLORS.EXCELLENT.color;
  if (percentage >= SCORE_COLORS.GOOD.threshold) return SCORE_COLORS.GOOD.color;
  return SCORE_COLORS.POOR.color;
}

// ── Score Rendering ────────────────────────────────────────
function renderScore(score) {
  const number = Math.round(score);
  document.getElementById("score-number").textContent = number + "%";
  
  const level = getLevel(score, SCORE_LEVELS);
  const status = document.getElementById("score-status");
  status.textContent = level.label;
  status.style.color = level.color;
  
  const msg = getLevel(score, SCORE_MESSAGES);
  document.getElementById("score-message").textContent = msg.text;
  
  // Set circle properties (animation triggered by IntersectionObserver)
  const circle = document.getElementById("score-circle");
  const circumference = 2 * Math.PI * 72;
  const offset = circumference - (score / 100) * circumference;
  
  circle.dataset.targetOffset = offset;
  circle.dataset.targetColor = level.color;
  
  // Set initial state (full circle)
  circle.style.strokeDashoffset = circumference;
  circle.style.stroke = level.color;
}

function animateScoreOnView() {
  const scoreCard = document.querySelector('.score-card');
  const circle = document.getElementById('score-circle');
  
  if (!scoreCard || !circle) return;
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        // Add transition
        circle.style.transition = 'stroke-dashoffset 1.5s cubic-bezier(0.65, 0, 0.35, 1)';
        
        // Trigger reflow
        circle.getBoundingClientRect();
        
        // Animate to target
        setTimeout(() => {
          circle.style.strokeDashoffset = circle.dataset.targetOffset;
          circle.style.stroke = circle.dataset.targetColor;
        }, 100);
        
        // Disconnect observer
        observer.disconnect();
      }
    });
  }, { threshold: 0.5 });
  
  observer.observe(scoreCard);
}

// ── Tag Rendering ──────────────────────────────────────────
function renderTags(containerId, items, className) {
  const el = document.getElementById(containerId);
  const countEl = document.getElementById(containerId.replace('-tags', '-count'));
  
  if (!el) return;
  
  if (!items || items.length === 0) {
    el.innerHTML = `<span style="color:var(--sage-500);font-size:14px;">None detected</span>`;
    if (countEl) countEl.textContent = "0";
    return;
  }
  
  if (countEl) countEl.textContent = items.length;
  el.innerHTML = items
    .map(item => `<span class="tag ${className}">${sanitizeHTML(item)}</span>`)
    .join("");
}

// ── Score Breakdown ────────────────────────────────────────
function renderScoreBreakdown(breakdown) {
  if (!breakdown) return;
  
  const container = document.getElementById("score-breakdown");
  if (!container) return;
  
  const rows = [
    { label: "Keyword Match",      key: "keyword_overlap",   max: 30 },
    { label: "Keyword Placement",  key: "keyword_placement", max: 20 },
    { label: "Experience",         key: "experience",        max: 10 },
    { label: "Education",          key: "education",         max: 10 },
    { label: "Formatting",         key: "formatting",        max: 2  },
    { label: "Contact Info",       key: "contact",           max: 5  },
    { label: "Structure",          key: "structure",         max: 3  },
    { label: "Impact",             key: "impact",            max: 5  },
    { label: "Seniority",          key: "seniority",         max: 5  },
  ];
  
  const html = rows.map(row => {
    const val = breakdown[row.key] || 0;
    const pct = Math.min(100, Math.round((val / row.max) * 100));
    const color = getScoreColor(pct);
    
    return `
      <div class="breakdown-item">
        <div class="breakdown-header">
          <span class="breakdown-name">${row.label}</span>
          <span class="breakdown-value" style="color:${color};">${pct}%</span>
        </div>
        <div class="breakdown-bar">
          <div class="breakdown-fill" style="width:${pct}%;background:${color};"></div>
        </div>
      </div>
    `;
  }).join("");
  
  container.innerHTML = html;
}

// ── Suggestions Button (Always Visible) ───────────────────
function renderSuggestions(suggestions, score) {
  // Use the new modal HTML already in audit.html
  if (window.renderSuggestions && window.renderSuggestions !== renderSuggestions) {
    window.renderSuggestions(suggestions);
  } else {
    // Fallback: render into modal-body directly
    if (!suggestions || !suggestions.length) return;
    const body = document.getElementById('suggestions-body');
    if (!body) return;

    // Cap suggestions by score tier
    const score = JSON.parse(localStorage.getItem('auditResults') || '{}').score || 0;
    const maxSuggestions = score >= 80 ? 2 : score >= 55 ? 3 : 5;
    const visible = suggestions.slice(0, maxSuggestions);

    body.innerHTML = visible.map((s, i) => {
      const p = s.priority || 'medium';
      const hasOriginal = s.original && s.original !== 'N/A - new addition' && s.original !== 'N/A';

      // Format fix text: if it contains newlines or "•/-" bullets, render as <ul>
      const fixRaw = (s.fix || '').trim();
      const lines = fixRaw.split(/\n+/).map(l => l.replace(/^[\-•]\s*/, '').trim()).filter(Boolean);
      const fixHtml = lines.length > 1
        ? `<ul class="fix-list">${lines.map(l => `<li>${sanitizeHTML(l)}</li>`).join('')}</ul>`
        : `<span>${sanitizeHTML(fixRaw)}</span>`;

      return `<div class="suggestion-card priority-${p}">
        <div class="suggestion-header">
          <span class="suggestion-priority">${p.toUpperCase()}</span>
          <div class="suggestion-area">${sanitizeHTML(s.area || '')}</div>
        </div>
        <p class="suggestion-issue">⚠️ ${sanitizeHTML(s.issue || '')}</p>
        ${hasOriginal ? `
        <div class="suggestion-original">
          <div class="suggestion-label">📄 Current text:</div>
          <div class="original-text">${sanitizeHTML(s.original)}</div>
        </div>` : ''}
        <div class="suggestion-fix-block">
          <div class="suggestion-label">✏️ Replace with:</div>
          <div class="fix-text">${fixHtml}</div>
          <button class="copy-fix-btn" onclick="copyFix(this)">📋 Copy</button>
        </div>
      </div>`;
    }).join('');

    // Show upgrade nudge if suggestions were capped
    if (suggestions.length > maxSuggestions && score >= 55) {
      body.innerHTML += `<div class="suggestions-nudge">
        ✨ ${suggestions.length - maxSuggestions} more suggestion${suggestions.length - maxSuggestions > 1 ? 's' : ''} available — apply the fixes above and re-analyse to unlock them.
      </div>`;
    }
  }
  // Enable the suggestions and optimize buttons
  const btn = document.getElementById('suggestions-btn');
  if (btn) btn.disabled = false;
  const optBtn = document.getElementById('optimize-btn');
  if (optBtn) optBtn.disabled = false;
}

// ── Copy to clipboard helper ───────────────────────────────
function copyFix(btn) {
  const fixText = btn.closest('.suggestion-card').querySelector('.fix-text').innerText;
  navigator.clipboard.writeText(fixText).then(() => {
    const orig = btn.textContent;
    btn.textContent = '✓ Copied!';
    btn.style.background = 'var(--green-500)';
    btn.style.color = '#fff';
    setTimeout(() => {
      btn.textContent = orig;
      btn.style.background = '';
      btn.style.color = '';
    }, 2000);
  });
}

// ── Suggestions Modal ──────────────────────────────────────
window.showSuggestionsModal = function() {
  const data = JSON.parse(localStorage.getItem('auditResults') || '{}');
  const score = Math.round(data.score || 0);
  const modal = document.getElementById('suggestions-modal');
  if (modal) {
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  trackEvent('Suggestions Modal Opened', { score });
};

function showSuggestionsAndOptimizeModal(score, suggestions) {
  const modal = document.createElement('div');
  modal.className = 'suggestions-modal';
  
  // Determine content based on score
  let content = '';
  
  if (score >= 80) {
    // High score: Show congratulations
    content = `
      <div class="modal-scroll-content">
        <div class="excellent-score-message">
          <div class="excellent-icon">🎉</div>
          <h3>Excellent Resume-Job Match!</h3>
          <p>
            Your resume scores <strong>${Math.round(score)}%</strong> — you're in the top 5% of candidates for this role.
            Your profile demonstrates strong alignment with the job requirements across all key dimensions.
          </p>
          <div class="excellent-stats">
            <div class="stat-item">
              <div class="stat-icon">✓</div>
              <div>Strong keyword coverage</div>
            </div>
            <div class="stat-item">
              <div class="stat-icon">✓</div>
              <div>Excellent semantic match</div>
            </div>
            <div class="stat-item">
              <div class="stat-icon">✓</div>
              <div>ATS-optimized structure</div>
            </div>
          </div>
          <p class="excellent-cta-text">
            <strong>Your resume is ready!</strong> While your match is excellent, you can still download 
            an AI-optimized version tailored specifically to this job description.
          </p>
        </div>
      </div>
    `;
  } else {
    // Lower score: Show suggestions
    const suggestionsHTML = suggestions.map((s, i) => {
      const safeIssue = sanitizeHTML(s.issue);
      const safeImpact = sanitizeHTML(s.impact);
      const safeArea = sanitizeHTML(s.area);
      
      // Clean the fix text - remove leading bullets/dashes
      let cleanFix = s.fix
        .replace(/^[•\-\*]\s*/, '')  // Remove leading bullet
        .replace(/^\s*[\-\•]\s*/gm, '') // Remove bullets from new lines
        .trim();
      
      // Split by semicolons or periods followed by capital letters to create bullet points
      // This handles text like "Did A; Did B; Did C" or "Did A. Did B. Did C"
      let bulletPoints = [];
      
      // Try splitting by semicolons first
      if (cleanFix.includes(';')) {
        bulletPoints = cleanFix.split(';').map(point => point.trim()).filter(point => point.length > 0);
      } 
      // If no semicolons, try splitting by sentences (period + space + capital letter)
      else if (cleanFix.match(/\.\s+[A-Z]/)) {
        // Split but keep the periods with their sentences
        bulletPoints = cleanFix.split(/(?<=\.)\s+(?=[A-Z])/).map(point => point.trim()).filter(point => point.length > 0);
      }
      // If neither, keep as single point
      else {
        bulletPoints = [cleanFix];
      }
      
      // Create HTML for bullet points
      const bulletPointsHTML = bulletPoints.map(point => {
        const safeBullet = sanitizeHTML(point);
        return `<li class="suggestion-bullet">${safeBullet}</li>`;
      }).join('');
      
      // For clipboard: join with line breaks
      const clipboardText = bulletPoints.join('\n• ');
      
      const escapedFix = clipboardText
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '&quot;')
        .replace(/\n/g, '\\n');
      
      return `
        <div class="suggestion ${s.priority}">
          <div class="suggestion-header">
            <span class="suggestion-area">${String(i + 1).padStart(2, "0")} // ${safeArea}</span>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="suggestion-priority ${s.priority}">${s.priority}</span>
              <button 
                class="copy-btn" 
                onclick="copyToClipboard('${escapedFix}', this)"
                aria-label="Copy suggestion to clipboard"
              >
                📋 Copy
              </button>
            </div>
          </div>
          <div class="suggestion-issue"><strong>Issue:</strong> ${safeIssue}</div>
          <div class="suggestion-fix-container">
            <div class="suggestion-fix-label">
              <strong>Suggested Fix:</strong> 
              <span class="add-bullet-hint">(${bulletPoints.length} bullet${bulletPoints.length > 1 ? 's' : ''} - copy all or pick one)</span>
            </div>
            <ul class="suggestion-bullets">
              ${bulletPointsHTML}
            </ul>
          </div>
          <div class="suggestion-impact"><strong>Impact:</strong> ${safeImpact}</div>
        </div>
      `;
    }).join('');
    
    content = `
      <div class="modal-scroll-content">
        <div class="suggestions-intro">
          <p>Based on your <strong>${Math.round(score)}%</strong> match score, here are 5 AI-powered improvements 
          to strengthen your resume for this role:</p>
        </div>
        ${suggestionsHTML || '<p style="text-align:center;color:var(--sage-500);">No suggestions available</p>'}
      </div>
    `;
  }
  
  modal.innerHTML = `
    <div class="modal-overlay-dark" onclick="closeSuggestionsModal()"></div>
    <div class="suggestions-modal-content">
      <div class="modal-header-sticky">
        <div>
          <h2>${score >= 80 ? 'Your Resume Is Excellent!' : 'AI-Powered Improvements'}</h2>
          <p class="modal-subtitle">${score >= 80 ? 'Ready to optimize and download' : 'Copy-paste ready fixes ranked by impact'}</p>
        </div>
        <button class="modal-close-btn" onclick="closeSuggestionsModal()" aria-label="Close">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
      
      ${content}
      
      <div class="modal-footer-sticky">
        <div class="optimize-cta">
          <div class="optimize-text">
            <strong>🔒 Want an optimized resume?</strong>
            <p>Get an AI-tailored DOCX file perfect for this job</p>
          </div>
          <button class="btn-primary" onclick="optimizeResume(); closeSuggestionsModal();">
            Optimize & Download
          </button>
        </div>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  document.body.style.overflow = 'hidden';
}

window.closeSuggestionsModal = function() {
  // Use the static modal in audit.html — just hide it, never remove it
  const modal = document.getElementById('suggestions-modal');
  if (modal) {
    modal.classList.remove('open');
    document.body.style.overflow = '';
    return;
  }
  // Fallback: dynamic modal (remove it)
  const dynamic = document.querySelector('.suggestions-modal');
  if (dynamic) {
    dynamic.classList.remove('open');
    document.body.style.overflow = '';
  }
};

// Close on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeSuggestionsModal();
  }
});

// ── Copy to Clipboard ──────────────────────────────────────
window.copyToClipboard = function(text, button) {
  navigator.clipboard.writeText(text).then(() => {
    const originalHTML = button.innerHTML;
    button.innerHTML = '✓ Copied!';
    button.style.background = 'var(--green-500)';
    button.style.color = 'white';
    button.style.borderColor = 'var(--green-500)';
    
    trackEvent('Suggestion Copied', {
      textLength: text.length,
    });
    
    setTimeout(() => {
      button.innerHTML = originalHTML;
      button.style.background = '';
      button.style.color = '';
      button.style.borderColor = '';
    }, 2000);
  }).catch(err => {
    console.error('Copy failed:', err);
    button.innerHTML = '✗ Failed';
    setTimeout(() => {
      button.innerHTML = '📋 Copy';
    }, 2000);
  });
};

// ── Audit Sections ─────────────────────────────────────────

// ── ATS System Score Cards ─────────────────────────────────
function renderATSSystemScores(atsScores) {
  if (!atsScores) return;
  const el = (id, val) => {
    const el = document.getElementById(id);
    if (el && val && val !== 'N/A') el.textContent = val;
  };
  el('ats-workday',    atsScores.workday_score);
  el('ats-greenhouse', atsScores.greenhouse_rank);
  el('ats-taleo',      atsScores.taleo_match);
  el('ats-icims',      atsScores.icims_score);
}

function renderAuditSections(audit) {
  const container = document.getElementById("audit-sections");
  if (!container) return;
  
  Object.entries(audit).forEach(([category, items]) => {
    const card = document.createElement("div");
    card.className = "report-card";
    
    const itemsHtml = items.map(item => {
      const icon = item.status === "hit" ? "✓" : "✕";
      const iconClass = item.status === "hit" ? "hit" : "miss";
      
      // Sanitize message
      let safeMsg = sanitizeHTML(item.msg);
      
      // Bold the label before the first colon (e.g., "Geo-Searchability Verified:")
      safeMsg = safeMsg.replace(/^([^:]+:)/, '<strong>$1</strong>');
      
      return `
        <div class="audit-item">
          <div class="audit-icon ${iconClass}">${icon}</div>
          <div class="audit-content">
            <p class="audit-message">${safeMsg}</p>
          </div>
        </div>
      `;
    }).join("");
    
    card.innerHTML = `
      <div class="card-header">
        <h2>${sanitizeHTML(category)}</h2>
      </div>
      ${itemsHtml}
    `;
    
    container.appendChild(card);
  });
}

// ── Density Chart ──────────────────────────────────────────
function renderDensityChart(density) {
  if (!density) return;
  
  const explanationEl = document.getElementById("density-explanation");
  if (explanationEl) {
    explanationEl.textContent = density.explanation;
  }
  
  const canvas = document.getElementById("densityChart");
  if (!canvas) return;
  
  const ctx = canvas.getContext("2d");
  
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: density.labels,
      datasets: [
        { 
          label: "JD Target",    
          data: density.jd_counts,  
          backgroundColor: "rgba(206,212,218,0.3)", 
          borderColor: "var(--sage-300)", 
          borderWidth: 1, 
          borderRadius: 8 
        },
        { 
          label: "Your Resume",  
          data: density.res_counts, 
          backgroundColor: "var(--green-500)", 
          borderRadius: 8 
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: "var(--sage-700)",
            font: { family: "Inter", size: 13 }
          }
        },
        tooltip: {
          callbacks: {
            title: (items) => `Keyword: ${items[0].label}`,
            label: (item) => {
              const label = item.dataset.label;
              const value = item.parsed.y;
              return `${label}: ${value} occurrence${value !== 1 ? 's' : ''}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: "var(--sage-200)" },
          ticks: { 
            color: "var(--sage-600)",
            precision: 0
          },
          title: {
            display: true,
            text: 'Frequency',
            color: "var(--sage-600)"
          }
        },
        x: {
          grid: { display: false },
          ticks: { color: "var(--sage-600)" }
        },
      },
    },
  });
}

// ── Optimize Resume (Feature Lock) ────────────────────────
window.optimizeResume = async function() {
  const data        = JSON.parse(localStorage.getItem('auditResults') || '{}');
  const resumeText  = localStorage.getItem('resumeText') || '';
  const jdText      = localStorage.getItem('jdText') || '';
  const email       = localStorage.getItem('userEmail') || '';
  const usage       = JSON.parse(localStorage.getItem('usageData') || '{}');
  const score       = Math.round(data.score || 0);

  // Guard: need resume+JD text
  if (!resumeText || !jdText) {
    showOptimizeError('Resume or job description text not found. Please run a new analysis first.');
    return;
  }

  // Guard: check optimization credits
  const tier      = usage.userTier || 'free';
  const optUsed   = usage.optimizationsUsed  || 0;
  const optLimits = { free: 1, job_seeker: 5, unlimited: 15, recruiter: 50 };
  const optLimit  = optLimits[tier] || 1;

  if (optUsed >= optLimit) {
    showOptimizeError(
      `You've used all ${optLimit} optimization${optLimit > 1 ? 's' : ''} for this month. ` +
      `<a href="index.html#pricing" style="color:var(--green);font-weight:600">Upgrade your plan</a> to get more.`
    );
    return;
  }

  // Show loading overlay
  showOptimizeLoading(score);

  try {
    const API = window.API_BASE || 'https://matchmyjobs.onrender.com';
    const res = await fetch(`${API}/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_text:    resumeText,
        jd_text:        jdText,
        original_score: score,
        email:          email || null,
      })
    });

    const result = await res.json();

    if (!res.ok) {
      throw new Error(result.detail || 'Optimization failed');
    }

    // Update optimization count in localStorage
    if (result.optimizations_used !== undefined) {
      usage.optimizationsUsed  = result.optimizations_used;
      usage.optimizationsLimit = result.optimizations_limit;
      localStorage.setItem('usageData', JSON.stringify(usage));
    } else {
      usage.optimizationsUsed = (usage.optimizationsUsed || 0) + 1;
      localStorage.setItem('usageData', JSON.stringify(usage));
    }

    // Hide loading, show results
    hideOptimizeLoading();
    showOptimizeResult(result);

  } catch (err) {
    hideOptimizeLoading();
    showOptimizeError(err.message || 'Optimization failed. Please try again.');
  }

  trackEvent('Optimize Resume Clicked', { score });
};

function showOptimizeLoading(originalScore) {
  const el = document.createElement('div');
  el.id = 'optimize-overlay';
  el.className = 'optimize-overlay';
  el.innerHTML = `
    <div class="optimize-panel">
      <div class="optimize-spinner"></div>
      <h2 class="optimize-title">Optimizing Your Resume</h2>
      <p class="optimize-sub">AI is rewriting your resume to target 80%+ score…</p>
      <div class="optimize-steps">
        <div class="opt-step active" id="opt-s1">⚡ Analysing skill gaps</div>
        <div class="opt-step" id="opt-s2">✏️ Rewriting content</div>
        <div class="opt-step" id="opt-s3">📊 Scoring the rewrite</div>
        <div class="opt-step" id="opt-s4">📄 Generating DOCX</div>
      </div>
    </div>`;
  document.body.appendChild(el);
  document.body.style.overflow = 'hidden';

  // Animate steps
  let i = 1;
  const timer = setInterval(() => {
    if (i > 0) document.getElementById(`opt-s${i}`)?.classList.remove('active');
    i++;
    if (i <= 4) document.getElementById(`opt-s${i}`)?.classList.add('active');
    else clearInterval(timer);
  }, 2800);
  el._timer = timer;
}

function hideOptimizeLoading() {
  const el = document.getElementById('optimize-overlay');
  if (el) { clearInterval(el._timer); el.remove(); }
  document.body.style.overflow = '';
}

function showOptimizeResult(result) {
  const improved = result.new_score > result.original_score;
  const el = document.createElement('div');
  el.id = 'optimize-result-overlay';
  el.className = 'optimize-overlay';
  el.innerHTML = `
    <div class="optimize-panel optimize-result-panel">
      <button class="optimize-close" onclick="document.getElementById('optimize-result-overlay').remove();document.body.style.overflow=''">✕</button>
      <div class="opt-result-header">
        <div class="opt-score-compare">
          <div class="opt-score-box opt-score-before">
            <span class="opt-score-label">Before</span>
            <span class="opt-score-num">${result.original_score}%</span>
          </div>
          <div class="opt-score-arrow">${improved ? '→' : '↔'}</div>
          <div class="opt-score-box opt-score-after ${result.new_score >= 80 ? 'green' : 'amber'}">
            <span class="opt-score-label">After</span>
            <span class="opt-score-num">${result.new_score}%</span>
          </div>
        </div>
        <p class="opt-result-msg">
          ${result.target_reached
            ? '✅ Your resume now scores <strong>80%+</strong> — ATS ready!'
            : improved
              ? `📈 Improved by <strong>${result.improvement}%</strong>. Apply the AI suggestions to push further.`
              : '⚠️ Score unchanged — your resume may already be well-optimised or needs manual skill additions.'}
        </p>
      </div>

      <div class="opt-text-preview">
        <div class="opt-preview-label">Optimized Resume Preview</div>
        <pre class="opt-preview-text" id="opt-preview">${sanitizeHTML(result.optimized_text || '')}</pre>
      </div>

      <div class="opt-actions">
        ${result.docx_b64 ? `
        <button class="btn-primary btn-large" onclick="downloadDocx()">
          📥 Download Optimized DOCX
        </button>` : ''}
        <button class="btn-secondary" onclick="copyOptimizedText()">
          📋 Copy Text
        </button>
        <button class="btn-secondary" onclick="document.getElementById('optimize-result-overlay').remove();document.body.style.overflow=''">
          Close
        </button>
      </div>
    </div>`;
  document.body.appendChild(el);
  document.body.style.overflow = 'hidden';

  // Store for download
  if (result.docx_b64) window._optimizeDocx = result.docx_b64;
  window._optimizeText = result.optimized_text;
}

function showOptimizeError(msg) {
  const el = document.createElement('div');
  el.className = 'optimize-overlay';
  el.innerHTML = `
    <div class="optimize-panel" style="text-align:center;gap:16px">
      <div style="font-size:2.5rem">⚠️</div>
      <h2 class="optimize-title">Could not optimize</h2>
      <p class="optimize-sub">${msg}</p>
      <button class="btn-secondary" onclick="this.closest('.optimize-overlay').remove();document.body.style.overflow=''">Close</button>
    </div>`;
  document.body.appendChild(el);
  document.body.style.overflow = 'hidden';
}

window.downloadDocx = function() {
  if (!window._optimizeDocx) return;
  const bytes  = atob(window._optimizeDocx);
  const arr    = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  const blob   = new Blob([arr], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  const url    = URL.createObjectURL(blob);
  const a      = document.createElement('a');
  a.href       = url;
  a.download   = 'optimized_resume.docx';
  a.click();
  URL.revokeObjectURL(url);
  trackEvent('Optimized Resume Downloaded');
};

window.copyOptimizedText = function() {
  if (!window._optimizeText) return;
  navigator.clipboard.writeText(window._optimizeText).then(() => {
    const btn = document.querySelector('.opt-actions .btn-secondary');
    if (btn) { btn.textContent = '✓ Copied!'; setTimeout(() => { btn.textContent = '📋 Copy Text'; }, 2000); }
  });
};

// ── Share Results ──────────────────────────────────────────
window.shareResults = async function() {
  const data = JSON.parse(localStorage.getItem("auditResults") || '{}');
  
  const score = Math.round(data.score || 0);
  const matched = data.recent_hits?.length || 0;
  const missing = data.missing?.length || 0;
  
  const shareText = `I scored ${score}% on MatchMyJobs's ATS resume analyzer!

Matched: ${matched} skills
Missing: ${missing} skills

Try it free: https://matchmyjobs.com`;

  if (navigator.share) {
    try {
      await navigator.share({
        title: 'My MatchMyJobs Resume Score',
        text: shareText,
        url: window.location.href
      });
      trackEvent('Results Shared', { method: 'native', score });
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Share failed:', err);
      }
    }
  } else {
    // Fallback: Copy to clipboard
    try {
      await navigator.clipboard.writeText(shareText);
      
      // Show notification
      const btn = event.target;
      const originalText = btn.textContent;
      btn.textContent = '✓ Copied to clipboard!';
      btn.style.background = 'var(--green-500)';
      
      setTimeout(() => {
        btn.textContent = originalText;
        btn.style.background = '';
      }, 2000);
      
      trackEvent('Results Shared', { method: 'clipboard', score });
    } catch (err) {
      console.error('Copy failed:', err);
      alert('Unable to share. Please copy the URL manually.');
    }
  }
};

// ── Page Initialization ────────────────────────────────────
window.onload = function () {
  const stored = localStorage.getItem("auditResults");
  
  if (!stored) {
    window.location.href = "index.html";
    return;
  }
  
  try {
    const data = JSON.parse(stored);
    
    // Generate report ID
    const reportId = "MM-" + Math.random().toString(36).substr(2, 7).toUpperCase();
    const reportIdEl = document.getElementById("report-id");
    if (reportIdEl) {
      reportIdEl.textContent = reportId;
    }
    
    // Render all sections
    renderScore(data.score);
    renderTags("matched-tags", data.recent_hits, "matched");
    renderTags("missing-tags", data.missing, "missing");
    renderTags("soft-tags", data.soft_skills, "matched");
    renderScoreBreakdown(data.score_breakdown);
    renderATSSystemScores(data.ats_specific_scores);
    renderSuggestions(data.suggestions, data.score);
    renderAuditSections(data.audit);
    renderDensityChart(data.density);
    
    // Trigger score animation on view
    animateScoreOnView();
    
    // Analytics
    trackEvent('Results Viewed', {
      score: Math.round(data.score),
      reportId: reportId,
      matchedSkills: data.recent_hits?.length || 0,
      missingSkills: data.missing?.length || 0,
      suggestionsCount: data.suggestions?.length || 0,
    });
    
  } catch (err) {
    console.error('Failed to render results:', err);
    alert('Error loading results. Please run a new analysis.');
    window.location.href = "index.html";
  }
};

// Track scroll depth
let maxScrollDepth = 0;
window.addEventListener('scroll', () => {
  const scrollDepth = Math.round(
    (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100
  );
  
  if (scrollDepth > maxScrollDepth) {
    maxScrollDepth = scrollDepth;
    
    // Track milestones
    if ([25, 50, 75, 100].includes(scrollDepth)) {
      trackEvent('Scroll Depth', { depth: scrollDepth });
    }
  }
});
