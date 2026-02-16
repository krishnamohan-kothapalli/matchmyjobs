// ============================================================
// MatchMyJobs v4.0 - Professional UI with Upload
// ============================================================

// ── Configuration ──────────────────────────────────────────
const CONFIG = {
  API_BASE: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? "http://127.0.0.1:8000"
    : "https://matchmyjobs-api.onrender.com", // Update with your production API
  
  MAX_FILE_SIZE: {
    resume: 10 * 1024 * 1024, // 10MB
    jd: 5 * 1024 * 1024,      // 5MB
  },
  
  SUPPORTED_FORMATS: {
    resume: ['.pdf', '.doc', '.docx'],
    jd: ['.pdf', '.doc', '.docx', '.txt'],
  },
  
  FREE_ANALYSES: 2, // Free analyses before requiring auth
};

// ── State Management ───────────────────────────────────────
const state = {
  resumeText: '',
  jdText: '',
  resumeFile: null,
  jdFile: null,
  currentTab: 'upload',
  isAuthenticated: false,
  userTier: 'free', // 'free', 'analysis_pro', 'optimize'
  analysesUsed: 0,
};

// ── Authentication & Usage Tracking ────────────────────────
function checkAuthAndAnalyze() {
  // Check if user is authenticated
  const authToken = localStorage.getItem('authToken');
  
  if (!authToken) {
    // Not logged in - redirect to auth page
    window.location.href = 'auth.html';
    return;
  }
  
  // Check local storage for usage count
  const usageData = JSON.parse(localStorage.getItem('usageData') || '{}');
  const analysesUsed = usageData.analysesUsed || 0;
  const userTier = usageData.userTier || 'free';
  
  // Free tier: 2 analyses
  if (userTier === 'free' && analysesUsed >= CONFIG.FREE_ANALYSES) {
    showUpgradeModal('analysis');
    return;
  }
  
  // Analysis Pro: 50/month
  if (userTier === 'analysis_pro' && analysesUsed >= 50) {
    showLimitReached('analysis');
    return;
  }
  
  // Optimize: 50 analyses + 25 optimizations/month
  if (userTier === 'optimize' && analysesUsed >= 50) {
    showLimitReached('optimize');
    return;
  }
  
  // Proceed with analysis
  openUploadModal();
}

function showSignupModal() {
  window.location.href = 'auth.html';
}

function showLimitReached(tier) {
  const message = tier === 'analysis' 
    ? "You've used all 50 analyses this month. Your limit will reset on the 1st."
    : "You've used all 50 analyses this month. Your limit will reset on the 1st.";
    
  alert(message + "\n\nNeed more? Contact support@matchmyjobs.com");
}

function incrementUsageCount() {
  const usageData = JSON.parse(localStorage.getItem('usageData') || '{}');
  usageData.analysesUsed = (usageData.analysesUsed || 0) + 1;
  usageData.userTier = usageData.userTier || 'free';
  usageData.lastUsed = new Date().toISOString();
  localStorage.setItem('usageData', JSON.stringify(usageData));
  
  trackEvent('Analysis Completed', {
    count: usageData.analysesUsed,
    tier: usageData.userTier
  });
}

function showUpgradeModal(plan) {
  const modal = document.createElement('div');
  modal.className = 'upgrade-modal';
  
  const planDetails = {
    analysis: {
      title: 'Upgrade to Analysis Pro',
      price: '$20',
      limit: '50 analyses per month',
      features: [
        '50 analyses every month',
        'Monthly limit resets automatically',
        'Analysis history saved',
        'Priority processing',
        'PDF export',
        'Lifetime access - pay once'
      ]
    },
    optimize: {
      title: 'Upgrade to Premium',
      price: '$30',
      limit: '50 analyses + 25 optimizations per month',
      features: [
        'Everything in Analysis Pro',
        '25 AI optimizations per month',
        'Download optimized DOCX files',
        'Auto-tailor to jobs',
        'ATS-guaranteed formatting',
        'Lifetime access - pay once'
      ]
    }
  };
  
  const details = planDetails[plan] || planDetails.analysis;
  const usageData = JSON.parse(localStorage.getItem('usageData') || '{}');
  const analysesUsed = usageData.analysesUsed || 0;
  
  modal.innerHTML = `
    <div class="modal-overlay-dark" onclick="closeUpgradeModal()"></div>
    <div class="upgrade-modal-content">
      <div class="modal-header-sticky">
        <div>
          <h2>${details.title}</h2>
          <p class="modal-subtitle">You've used ${analysesUsed}/${CONFIG.FREE_ANALYSES} free analyses</p>
        </div>
        <button class="modal-close-btn" onclick="closeUpgradeModal()" aria-label="Close">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
      
      <div class="modal-scroll-content">
        <div class="upgrade-pricing">
          <div class="upgrade-price-box">
            <div class="price-large">${details.price}</div>
            <div class="price-period">lifetime • ${details.limit}</div>
          </div>
          
          <ul class="upgrade-features">
            ${details.features.map(f => `<li>✓ ${f}</li>`).join('')}
          </ul>
          
          <div class="upgrade-options">
            <button class="btn-primary btn-large btn-block" onclick="handleUpgrade('${plan}', 'lifetime')">
              Buy for ${details.price} (Lifetime)
            </button>
          </div>
          
          <p class="upgrade-note">
            <strong>One-time payment. Use forever.</strong> Perfect for students and active job seekers.
            Your monthly limit resets automatically on the 1st of each month.
          </p>
        </div>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  document.body.style.overflow = 'hidden';
  
  trackEvent('Upgrade Modal Shown', { plan, analysesUsed });
}

window.closeUpgradeModal = function() {
  const modal = document.querySelector('.upgrade-modal');
  if (modal) {
    modal.remove();
    document.body.style.overflow = '';
  }
};

window.handleUpgrade = function(plan, billingType) {
  // TODO: Integrate with payment processor (Stripe/Paddle)
  // For now, redirect to checkout or show coming soon
  
  trackEvent('Upgrade Clicked', {
    plan,
    billingType,
    amount: plan === 'optimize' ? 30 : 20
  });
  
  alert(`Upgrade to ${plan} (${billingType}) - Payment integration coming soon!
  
We'll redirect you to secure checkout where you can complete your purchase.`);
  
  // In production:
  // window.location.href = `/checkout?plan=${plan}&billing=${billingType}`;
};

// ── Modal Control ──────────────────────────────────────────
function openUploadModal(mode = 'normal') {
  const modal = document.getElementById('uploadModal');
  modal.classList.add('active');
  document.body.style.overflow = 'hidden';
  
  if (mode === 'sample') {
    loadSampleData();
  }
  
  trackEvent('Modal Opened', { mode });
}

function closeUploadModal() {
  const modal = document.getElementById('uploadModal');
  modal.classList.remove('active');
  document.body.style.overflow = '';
  
  trackEvent('Modal Closed');
}

// Close on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeUploadModal();
  }
});

// ── File Upload Handling ───────────────────────────────────
function handleFileUpload(input, type) {
  const file = input.files[0];
  if (!file) return;
  
  // Validate file size
  const maxSize = CONFIG.MAX_FILE_SIZE[type];
  if (file.size > maxSize) {
    showError(`File too large. Maximum size is ${(maxSize / 1024 / 1024).toFixed(0)}MB`);
    input.value = '';
    return;
  }
  
  // Validate file type
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  const supported = CONFIG.SUPPORTED_FORMATS[type];
  if (!supported.includes(ext)) {
    showError(`Unsupported format. Please upload ${supported.join(', ')} files`);
    input.value = '';
    return;
  }
  
  // Store file
  if (type === 'resume') {
    state.resumeFile = file;
  } else {
    state.jdFile = file;
  }
  
  // Update UI
  const uploadArea = document.getElementById(`${type}-upload`);
  const filenameEl = document.getElementById(`${type}-filename`);
  
  uploadArea.classList.add('has-file');
  filenameEl.textContent = `✓ ${file.name}`;
  
  trackEvent('File Uploaded', {
    type,
    size: file.size,
    format: ext,
  });
}

// Drag and drop support (only for resume)
function setupDragDrop() {
  const area = document.getElementById('resume-upload');
  
  area.addEventListener('dragover', (e) => {
    e.preventDefault();
    area.style.borderColor = 'var(--accent)';
  });
  
  area.addEventListener('dragleave', () => {
    area.style.borderColor = '';
  });
  
  area.addEventListener('drop', (e) => {
    e.preventDefault();
    area.style.borderColor = '';
    
    const file = e.dataTransfer.files[0];
    if (file) {
      const input = document.getElementById('resume-file');
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      handleFileUpload(input, 'resume');
    }
  });
}

// Initialize drag-drop on load
window.addEventListener('DOMContentLoaded', setupDragDrop);

// ── File Parsing (PDF/DOCX) ────────────────────────────────
async function parseFile(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  
  if (ext === '.pdf') {
    return await parsePDF(file);
  } else if (ext === '.docx' || ext === '.doc') {
    return await parseDOCX(file);
  } else if (ext === '.txt') {
    return await parseTXT(file);
  }
  
  throw new Error('Unsupported file format');
}

async function parsePDF(file) {
  try {
    // Load PDF.js from CDN
    if (typeof pdfjsLib === 'undefined') {
      await loadScript('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js');
      pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    }
    
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    
    let text = '';
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const content = await page.getTextContent();
      const pageText = content.items.map(item => item.str).join(' ');
      text += pageText + '\n\n';
    }
    
    return text.trim();
  } catch (err) {
    console.error('PDF parsing error:', err);
    throw new Error('Failed to parse PDF. Please try a different file or paste text manually.');
  }
}

async function parseDOCX(file) {
  try {
    // Load mammoth.js from CDN
    if (typeof mammoth === 'undefined') {
      await loadScript('https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/mammoth.browser.min.js');
    }
    
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value.trim();
  } catch (err) {
    console.error('DOCX parsing error:', err);
    throw new Error('Failed to parse DOCX. Please try a different file or paste text manually.');
  }
}

async function parseTXT(file) {
  return await file.text();
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

// ── Sample Data ────────────────────────────────────────────
function clearAllInputs() {
  // Clear textareas
  document.getElementById('resume-paste').value = '';
  document.getElementById('jd-paste').value = '';
  
  // Clear file inputs
  const resumeInput = document.getElementById('resume-file');
  const resumeUpload = document.getElementById('resume-upload');
  const resumeFilename = document.getElementById('resume-filename');
  
  if (resumeInput) resumeInput.value = '';
  if (resumeUpload) resumeUpload.classList.remove('has-file');
  if (resumeFilename) resumeFilename.textContent = '';
  
  // Clear state
  state.resumeText = '';
  state.jdText = '';
  state.resumeFile = null;
  state.jdFile = null;
  
  trackEvent('Inputs Cleared');
  
  // Show feedback
  showTemporaryMessage('All inputs cleared');
}

function loadSampleData() {
  const sampleResume = `SARAH JOHNSON
Senior UX/UI Designer
sarah.johnson@email.com | (555) 987-6543 | San Francisco, CA
LinkedIn: linkedin.com/in/sarahjohnson | Portfolio: sarahdesigns.com

PROFESSIONAL SUMMARY
Senior UX/UI Designer with 6 years of experience creating user-centered digital experiences for web and mobile applications. Expert in high-fidelity design, user research, wireframing, prototyping, and design systems. Proven presentation skills communicating design rationale to stakeholders and cross-functional teams. Passionate about solving complex problems through thoughtful design and data-driven iteration.

PROFESSIONAL EXPERIENCE

Senior UX Designer | TechFlow Inc. | San Francisco, CA | March 2021 - Present
• Led end-to-end UX design including high-fidelity prototypes for mobile banking app serving 200K+ users, presenting designs to C-suite and investors, resulting in 45% engagement increase and 4.8 App Store rating
• Conducted comprehensive user research including 50+ interviews and usability testing sessions with diverse user groups, identifying key pain points that informed product roadmap
• Created comprehensive high-fidelity design system with 100+ reusable components in Figma; presented to 40+ stakeholders across product, engineering, and leadership, improving design-to-development efficiency by 50%
• Mentored 3 junior designers on user research methodologies, design thinking, and WCAG 2.1 accessibility standards

UX/UI Designer | StartupLabs | San Francisco, CA | June 2019 - February 2021
• Designed responsive web interfaces for SaaS productivity platform used by 10K+ businesses
• Established design system and component library that reduced design time by 40%
• Ran A/B tests on key user flows, improving conversion rates by 28%
• Created wireframes, mockups, and interactive prototypes using Figma and InVision

EDUCATION
Bachelor of Fine Arts in Graphic Design
California College of the Arts | San Francisco, CA | 2017

CORE COMPETENCIES
User Research • Usability Testing • Wireframing • Prototyping • High-Fidelity Design • Visual Design
Interaction Design • Mobile-First Design • Responsive Design • Design Systems • Design Thinking
Presentation Skills • Cross-functional Communication

TOOLS & SOFTWARE
Figma • Adobe XD • InVision • Maze • WCAG 2.1 Accessibility Standards`;

  const sampleJD = `Senior UX/UI Designer
TechCorp Solutions | San Francisco, CA

About the Role:
We're seeking a talented Senior UX/UI Designer to join our growing product team. You'll work on our flagship SaaS platform used by thousands of businesses worldwide.

Requirements:
• 5-8 years of professional UX/UI design experience
• Expert proficiency in Figma, Adobe XD, and modern design tools
• Strong portfolio demonstrating user research, wireframing, and high-fidelity design work
• Proven experience creating and maintaining design systems
• Excellent presentation skills to articulate design decisions
• Experience with responsive design and mobile-first approaches
• Deep understanding of user research methodologies and usability testing
• Knowledge of WCAG 2.1 accessibility standards

Preferred:
• Experience designing for SaaS products
• A/B testing and data-driven design experience
• Design thinking workshops facilitation`;

  // Load sample resume text (for paste option)
  document.getElementById('resume-paste').value = sampleResume;
  
  // Always load JD as paste text
  document.getElementById('jd-paste').value = sampleJD;
  
  trackEvent('Sample Data Loaded');
  
  // Show feedback
  showTemporaryMessage('Sample data loaded! Click Analyze to see results.');
}

function showTemporaryMessage(message) {
  const existing = document.querySelector('.temp-message');
  if (existing) existing.remove();
  
  const msg = document.createElement('div');
  msg.className = 'temp-message';
  msg.textContent = message;
  msg.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: var(--accent);
    color: white;
    padding: 1rem 1.5rem;
    border-radius: var(--radius);
    box-shadow: var(--shadow-lg);
    z-index: 9999;
    animation: slideInRight 0.3s ease-out;
  `;
  
  document.body.appendChild(msg);
  
  setTimeout(() => {
    msg.style.animation = 'slideOutRight 0.3s ease-out';
    setTimeout(() => msg.remove(), 300);
  }, 3000);
}

// ── Analysis Start ─────────────────────────────────────────
async function startAnalysis() {
  try {
    // Get resume: prioritize file, fallback to paste
    if (state.resumeFile) {
      showLoading('Parsing resume...');
      updateProgress(10);
      
      state.resumeText = await parseFile(state.resumeFile);
      updateProgress(40);
    } else {
      state.resumeText = document.getElementById('resume-paste').value.trim();
      
      if (!state.resumeText) {
        showError('Please upload a resume file or paste resume text');
        return;
      }
    }
    
    // Get JD: always from paste
    state.jdText = document.getElementById('jd-paste').value.trim();
    
    if (!state.jdText) {
      showError('Please paste the job description');
      hideLoading();
      return;
    }
    
    // Validate
    const errors = validateInput(state.resumeText, state.jdText);
    if (errors.length > 0) {
      showError(errors.join('. '));
      hideLoading();
      return;
    }
    
    // Close modal and show loading
    closeUploadModal();
    showLoading('Analyzing with AI...');
    updateProgress(60);
    
    // Run analysis
    await runAnalysis();
    
  } catch (err) {
    console.error('Analysis error:', err);
    showError(err.message || 'Analysis failed. Please try again.');
    hideLoading();
  }
}

async function runAnalysis() {
  try {
    updateLoadingStep('Extracting skills from resume', true);
    updateProgress(70);
    
    const res = await fetch(`${CONFIG.API_BASE}/score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_text: state.resumeText,
        jd_text: state.jdText,
      }),
    });
    
    updateProgress(85);
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server error: ${res.status}`);
    }
    
    updateLoadingStep('Analyzing job requirements', true);
    updateProgress(95);
    
    const data = await res.json();
    
    updateLoadingStep('Generating report', true);
    updateProgress(100);
    
    // Increment usage count
    incrementUsageCount();
    
    // Save and redirect
    localStorage.setItem('auditResults', JSON.stringify(data));
    saveToHistory(data);
    
    trackEvent('Analysis Completed', {
      score: Math.round(data.score),
      matchedSkills: data.recent_hits?.length || 0,
      missingSkills: data.missing?.length || 0,
    });
    
    setTimeout(() => {
      window.location.href = 'audit.html';
    }, 500);
    
  } catch (err) {
    throw err;
  }
}

// ── Input Validation ───────────────────────────────────────
function validateInput(resume, jd) {
  const errors = [];
  
  if (resume.length < 100) errors.push('Resume must be at least 100 characters');
  if (jd.length < 50) errors.push('Job description must be at least 50 characters');
  if (resume.length > 50000) errors.push('Resume exceeds 50,000 character limit');
  if (jd.length > 50000) errors.push('Job description exceeds 50,000 character limit');
  
  const resumeWords = resume.split(/\s+/).filter(w => w.length > 0);
  const jdWords = jd.split(/\s+/).filter(w => w.length > 0);
  
  if (resumeWords.length < 20) errors.push('Resume must contain at least 20 words');
  if (jdWords.length < 10) errors.push('Job description must contain at least 10 words');
  
  return errors;
}

// ── Loading Screen ─────────────────────────────────────────
function showLoading(text = 'Loading...') {
  const screen = document.getElementById('loadingScreen');
  const textEl = document.getElementById('loading-text');
  
  textEl.textContent = text;
  screen.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function hideLoading() {
  const screen = document.getElementById('loadingScreen');
  screen.classList.remove('active');
  document.body.style.overflow = '';
  updateProgress(0);
}

function updateProgress(percentage) {
  const fill = document.getElementById('progress-fill');
  const percent = document.getElementById('progress-percentage');
  
  fill.style.width = percentage + '%';
  percent.textContent = Math.round(percentage) + '%';
}

function updateLoadingStep(text, complete = false) {
  const container = document.getElementById('loading-steps');
  const existing = container.querySelector('.loading-step.active');
  
  if (existing && complete) {
    existing.classList.remove('active');
    existing.classList.add('complete');
  }
  
  const step = document.createElement('div');
  step.className = 'loading-step active';
  step.innerHTML = `
    <div class="step-icon">⟳</div>
    <div class="step-text">${text}</div>
  `;
  
  container.appendChild(step);
}

// ── Error Display ──────────────────────────────────────────
function showError(message) {
  // Use browser alert for now, can enhance with custom modal
  alert(message);
  trackEvent('Error Shown', { message });
}

// ── Analysis History ───────────────────────────────────────
function saveToHistory(data) {
  try {
    const history = JSON.parse(localStorage.getItem('analysisHistory') || '[]');
    
    history.unshift({
      id: Date.now(),
      timestamp: new Date().toISOString(),
      score: data.score,
      jobTitle: data.jd_parsed?.job_title || 'Unknown Role',
      matchedCount: data.recent_hits?.length || 0,
      missingCount: data.missing?.length || 0,
    });
    
    localStorage.setItem('analysisHistory', JSON.stringify(history.slice(0, 10)));
  } catch (err) {
    console.error('Failed to save history:', err);
  }
}

// ── Analytics ──────────────────────────────────────────────
function trackEvent(eventName, props = {}) {
  if (window.plausible) {
    window.plausible(eventName, { props });
  }
  
  if (CONFIG.API_BASE.includes('localhost')) {
    console.log('[Analytics]', eventName, props);
  }
}

// ── Page Load ──────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  trackEvent('Page Loaded', { page: 'index' });
});
