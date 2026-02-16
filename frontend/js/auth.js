// Auth Page JavaScript

// Switch between signin and signup tabs
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
}

// Handle Sign In
document.getElementById('form-signin').addEventListener('submit', async function(e) {
  e.preventDefault();
  
  const email = document.getElementById('signin-email').value;
  const password = document.getElementById('signin-password').value;
  
  try {
    // TODO: Replace with actual API call
    const response = await fetch('/api/auth/signin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (response.ok) {
      const data = await response.json();
      
      // Store user session
      localStorage.setItem('authToken', data.token);
      localStorage.setItem('userEmail', email);
      localStorage.setItem('usageData', JSON.stringify({
        analysesUsed: data.analysesUsed || 0,
        userTier: data.tier || 'free',
        lastUsed: new Date().toISOString()
      }));
      
      // Redirect to app
      window.location.href = 'index.html';
    } else {
      alert('Invalid email or password. Please try again.');
    }
  } catch (error) {
    console.error('Sign in error:', error);
    
    // For demo/testing: simulate successful login
    localStorage.setItem('authToken', 'demo-token');
    localStorage.setItem('userEmail', email);
    localStorage.setItem('usageData', JSON.stringify({
      analysesUsed: 0,
      userTier: 'free',
      lastUsed: new Date().toISOString()
    }));
    
    alert('Demo mode: Signed in successfully!');
    window.location.href = 'index.html';
  }
});

// Handle Sign Up
document.getElementById('form-signup').addEventListener('submit', async function(e) {
  e.preventDefault();
  
  const name = document.getElementById('signup-name').value;
  const email = document.getElementById('signup-email').value;
  const password = document.getElementById('signup-password').value;
  
  if (password.length < 8) {
    alert('Password must be at least 8 characters long.');
    return;
  }
  
  try {
    // TODO: Replace with actual API call
    const response = await fetch('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    });
    
    if (response.ok) {
      const data = await response.json();
      
      // Store user session
      localStorage.setItem('authToken', data.token);
      localStorage.setItem('userEmail', email);
      localStorage.setItem('userName', name);
      localStorage.setItem('usageData', JSON.stringify({
        analysesUsed: 0,
        userTier: 'free',
        maxAnalyses: 2,
        lastUsed: new Date().toISOString()
      }));
      
      // Redirect to app
      alert('Account created! You have 2 free analyses. Let\'s get started!');
      window.location.href = 'index.html';
    } else {
      const error = await response.json();
      alert(error.message || 'Sign up failed. Please try again.');
    }
  } catch (error) {
    console.error('Sign up error:', error);
    
    // For demo/testing: simulate successful signup
    localStorage.setItem('authToken', 'demo-token');
    localStorage.setItem('userEmail', email);
    localStorage.setItem('userName', name);
    localStorage.setItem('usageData', JSON.stringify({
      analysesUsed: 0,
      userTier: 'free',
      maxAnalyses: 2,
      lastUsed: new Date().toISOString()
    }));
    
    alert('Demo mode: Account created! You have 2 free analyses.');
    window.location.href = 'index.html';
  }
});

// Google Sign-In
function signInWithGoogle() {
  // Store return URL
  sessionStorage.setItem('authReturnUrl', window.location.href);
  
  // Redirect to backend OAuth endpoint
  window.location.href = 'https://matchmyjobs.onrender.com/auth/google/login';
}

// Handle OAuth callback
window.addEventListener('load', function() {
  const urlParams = new URLSearchParams(window.location.search);
  
  if (urlParams.has('token')) {
    // OAuth success - store token
    const token = urlParams.get('token');
    const email = urlParams.get('email');
    const name = urlParams.get('name');
    
    localStorage.setItem('authToken', token);
    localStorage.setItem('userEmail', email);
    localStorage.setItem('userName', name);
    localStorage.setItem('usageData', JSON.stringify({
      analysesUsed: 0,
      userTier: 'free',
      maxAnalyses: 2,
      lastUsed: new Date().toISOString()
    }));
    
    alert('Signed in successfully!');
    window.location.href = 'index.html';
  }
});
