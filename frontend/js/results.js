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
    body.innerHTML = suggestions.map(s => {
      const p = s.priority || 'medium';
      const systems = (s.ats_systems || []).map(sys => `<span class="system-badge">${sys}</span>`).join('');
      return `<div class="suggestion-card priority-${p}">
        <div class="suggestion-header">
          <span class="suggestion-priority">${p.toUpperCase()}</span>
          <div><div class="suggestion-area">${s.area || ''}</div>
          <div class="suggestion-systems">${systems}</div></div>
        </div>
        <p class="suggestion-issue">${s.issue || ''}</p>
        ${s.fix ? `<pre class="suggestion-fix">${s.fix}</pre>` : ''}
        ${s.why_it_matters ? `<p class="suggestion-issue">${s.why_it_matters}</p>` : ''}
        ${s.score_impact ? `<p class="suggestion-impact">📈 ${s.score_impact}</p>` : ''}
      </div>`;
    }).join('');
  }
  // Enable the suggestions button
  const btn = document.getElementById('suggestions-btn');
  if (btn) btn.disabled = false;
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
  const modal = document.querySelector('.suggestions-modal');
  if (modal) {
    modal.remove();
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
window.optimizeResume = function() {
  // Show feature lock modal
  showFeatureLockModal();
  
  trackEvent('Optimize Resume Clicked', {
    score: Math.round(JSON.parse(localStorage.getItem('auditResults') || '{}').score || 0)
  });
};

function showFeatureLockModal() {
  // Create modal overlay
  const modal = document.createElement('div');
  modal.className = 'feature-lock-modal';
  modal.innerHTML = `
    <div class="feature-lock-overlay" onclick="this.parentElement.remove()"></div>
    <div class="feature-lock-content">
      <div class="feature-lock-icon">🔒</div>
      <h2>Optimize & Download Resume</h2>
      <p class="feature-lock-description">
        Upgrade to <strong>Pro</strong> to unlock AI-powered resume optimization and download.
      </p>
      
      <div class="feature-lock-benefits">
        <div class="benefit-item">
          <div class="benefit-icon">✨</div>
          <div class="benefit-text">
            <strong>Auto-Optimize Resume</strong>
            <p>AI rewrites your resume to match the job description perfectly</p>
          </div>
        </div>
        <div class="benefit-item">
          <div class="benefit-icon">📄</div>
          <div class="benefit-text">
            <strong>Download DOCX</strong>
            <p>Get your optimized resume as an editable Word document</p>
          </div>
        </div>
        <div class="benefit-item">
          <div class="benefit-icon">🎯</div>
          <div class="benefit-text">
            <strong>ATS-Optimized</strong>
            <p>Guaranteed to pass all 6 major ATS platforms</p>
          </div>
        </div>
      </div>
      
      <div class="feature-lock-pricing">
        <div class="price-tag">
          <span class="price-amount">$10</span>
          <span class="price-period">lifetime access</span>
        </div>
        <ul class="price-features">
          <li>✓ Unlimited optimizations</li>
          <li>✓ All Pro features</li>
          <li>✓ Priority support</li>
        </ul>
      </div>
      
      <div class="feature-lock-actions">
        <button class="btn-primary btn-large" onclick="window.location.href='index.html#pricing'">
          Upgrade to Pro
        </button>
        <button class="btn-secondary" onclick="this.closest('.feature-lock-modal').remove()">
          Maybe Later
        </button>
      </div>
      
      <button class="feature-lock-close" onclick="this.closest('.feature-lock-modal').remove()" aria-label="Close">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
    </div>
  `;
  
  document.body.appendChild(modal);
  document.body.style.overflow = 'hidden';
  
  // Remove modal when overlay clicked
  modal.querySelector('.feature-lock-overlay').addEventListener('click', () => {
    modal.remove();
    document.body.style.overflow = '';
  });
  
  // Remove modal when escape pressed
  const handleEscape = (e) => {
    if (e.key === 'Escape') {
      modal.remove();
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEscape);
    }
  };
  document.addEventListener('keydown', handleEscape);
}

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
