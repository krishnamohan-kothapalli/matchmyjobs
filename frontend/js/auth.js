// Auth Page JavaScript

const API = 'https://matchmyjobs.onrender.com';

// ── Tab switching ────────────────────────────────────────────
function switchTab(tab) {
  const signinTab = document.getElementById('tab-signin');
  const signupTab = document.getElementById('tab-signup');
  const signinForm = document.getElementById('form-signin');
  const signupForm = document.getElementById('form-signup');

  if (tab === 'signin') {
    signinTab.classList.add('active');
    signupTab.classList.remove('active');
    signinForm.style.display = 'block';
    signupForm.style.display = 'none';
  } else {
    signinTab.classList.remove('active');
    signupTab.classList.add('active');
    signinForm.style.display = 'none';
    signupForm.style.display = 'block';
  }
  clearError();
}

function showError(msg) {
  let el = document.getElementById('auth-error');
  if (!el) {
    el = document.createElement('div');
    el.id = 'auth-error';
    el.style.cssText = 'background:#fef2f2;border:1px solid #fecaca;color:#dc2626;padding:0.75rem 1rem;border-radius:8px;font-size:0.85rem;margin-bottom:1rem;';
    document.querySelector('.auth-box').prepend(el);
  }
  el.textContent = msg;
  el.style.display = 'block';
}

function clearError() {
  const el = document.getElementById('auth-error');
  if (el) el.style.display = 'none';
}

function setLoading(formId, loading) {
  const btn = document.querySelector(`#${formId} button[type="submit"]`);
  if (btn) {
    btn.disabled = loading;
    btn.textContent = loading ? 'Please wait...' : (formId === 'form-signin' ? 'Sign In' : 'Create Account');
  }
}

function saveSession(data) {
  localStorage.setItem('authToken', data.token);
  localStorage.setItem('userEmail', data.email);
  localStorage.setItem('userName', data.name);
  localStorage.setItem('usageData', JSON.stringify({
    analysesUsed: data.analysesUsed || 0,
    analysesLimit: data.analysesLimit || 2,
    userTier: data.tier || 'free',
    lastUsed: new Date().toISOString()
  }));
}

// ── Sign In ──────────────────────────────────────────────────
document.getElementById('form-signin').addEventListener('submit', async function(e) {
  e.preventDefault();
  clearError();

  const email = document.getElementById('signin-email').value.trim();
  const password = document.getElementById('signin-password').value;

  if (!email || !password) {
    showError('Please enter your email and password.');
    return;
  }

  setLoading('form-signin', true);

  try {
    const response = await fetch(`${API}/api/auth/signin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (response.ok) {
      saveSession(data);
      window.location.href = 'index.html';
    } else {
      showError(data.detail || 'Sign in failed. Please try again.');
    }
  } catch (error) {
    showError('Cannot connect to server. Please try again.');
  } finally {
    setLoading('form-signin', false);
  }
});

// ── Sign Up ──────────────────────────────────────────────────
document.getElementById('form-signup').addEventListener('submit', async function(e) {
  e.preventDefault();
  clearError();

  const name = document.getElementById('signup-name').value.trim();
  const email = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;

  if (!name || !email || !password) {
    showError('Please fill in all fields.');
    return;
  }
  if (password.length < 8) {
    showError('Password must be at least 8 characters.');
    return;
  }

  setLoading('form-signup', true);

  try {
    const response = await fetch(`${API}/api/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    });

    const data = await response.json();

    if (response.ok) {
      saveSession(data);
      window.location.href = 'index.html';
    } else {
      showError(data.detail || 'Sign up failed. Please try again.');
    }
  } catch (error) {
    showError('Cannot connect to server. Please try again.');
  } finally {
    setLoading('form-signup', false);
  }
});

// ── Google OAuth ─────────────────────────────────────────────
function signInWithGoogle() {
  sessionStorage.setItem('authReturnUrl', window.location.href);
  window.location.href = `${API}/auth/google/login`;
}

// ── Google OAuth Callback ────────────────────────────────────
window.addEventListener('load', function() {
  const urlParams = new URLSearchParams(window.location.search);

  if (urlParams.has('token')) {
    const token = urlParams.get('token');
    const email = urlParams.get('email');
    const name = urlParams.get('name');

    localStorage.setItem('authToken', token);
    localStorage.setItem('userEmail', email);
    localStorage.setItem('userName', name);
    localStorage.setItem('usageData', JSON.stringify({
      analysesUsed: 0,
      analysesLimit: 2,
      userTier: 'free',
      lastUsed: new Date().toISOString()
    }));

    window.location.href = 'index.html';
  }

  if (urlParams.has('error')) {
    showError('Google sign-in failed. Please try again.');
  }
});

// ── Already logged in? ───────────────────────────────────────
if (localStorage.getItem('authToken') && localStorage.getItem('userEmail')) {
  // Already logged in - show dashboard link in UI if desired
  // window.location.href = 'index.html'; // Uncomment to auto-redirect
}
