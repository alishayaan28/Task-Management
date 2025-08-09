'use strict';

import { initializeApp } from "https://www.gstatic.com/firebasejs/9.22.2/firebase-app.js";
import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut } from "https://www.gstatic.com/firebasejs/9.22.2/firebase-auth.js";

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "",
    authDomain: "",
    databaseURL: "",
    projectId: "",
    storageBucket: "",
    messagingSenderId: "",
    appId: "",
    measurementId: ""
  };

// Declare Firebase app and auth globally
let auth;
let registeredUsers = {};

// Add token refresh handling
let tokenRefreshInterval;

window.addEventListener("load", function() {
    const app = initializeApp(firebaseConfig);
    auth = getAuth(auth);
    
    auth.onAuthStateChanged((user) => {
        if (user) {
            console.log("User is signed in");
            setupTokenRefresh(user); 
            updateUIForAuthenticatedUser(user);
        } else {
            console.log("User is signed out");
            clearTokenRefreshInterval();
            updateUIForUnauthenticatedUser();
        }
    });
    
    checkAuthState();
    
    try {
        const storedUsers = localStorage.getItem('registeredUsers');
        if (storedUsers) {
            registeredUsers = JSON.parse(storedUsers);
        }
    } catch (e) {
        console.error("Error loading registered users:", e);
        localStorage.removeItem('registeredUsers');
    }

    setupLoginUI();
});

function checkAuthState() {
    const token = parseCookieToken(document.cookie);
    
    if (token.length > 0) {
        auth.onIdTokenChanged((user) => {
            if (!user) {
                console.log("Invalid token detected, clearing and redirecting to login");
                clearAuthState();
            }
        });
    } else {
        updateUIForUnauthenticatedUser();
    }
}

// Function to clear authentication state completely
function clearAuthState() {
    document.cookie = "token=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT;SameSite=Strict";
    
    try {
        localStorage.removeItem('firebase:authUser');
    } catch (e) {
        console.error("Error clearing localStorage:", e);
    }
    
    updateUIForUnauthenticatedUser();
}

// Set up token refresh
function setupTokenRefresh(user) {
    clearTokenRefreshInterval(); 
    
    tokenRefreshInterval = setInterval(() => {
        user.getIdToken(true)
            .then((newToken) => {
                console.log("Token refreshed successfully");
                document.cookie = "token=" + newToken + ";path=/;SameSite=Strict";
            })
            .catch((error) => {
                console.error("Error refreshing token:", error);
                if (error.code === 'auth/network-request-failed') {
                    console.log("Network error refreshing token, will retry");
                } else {
                    clearAuthState();
                    signOut(auth).catch(e => console.error("Error signing out:", e));
                }
            });
    }, 1800000); 
}

// Clear token refresh interval
function clearTokenRefreshInterval() {
    if (tokenRefreshInterval) {
        clearInterval(tokenRefreshInterval);
        tokenRefreshInterval = null;
    }
}

// Setup login UI and validation
function setupLoginUI() {
    // Add validation for email and password fields
    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");
    
    if (emailInput && passwordInput) {
        setupErrorMessages();
        setupInputValidation(emailInput, passwordInput);
        setupSignUpButton();
        setupLoginButton();
    }
}

// Set up error message containers
function setupErrorMessages() {
    if (!document.getElementById("global-error-message")) {
        const errorMessageDiv = document.createElement("div");
        errorMessageDiv.id = "global-error-message";
        errorMessageDiv.style.color = "red";
        errorMessageDiv.style.fontWeight = "bold";
        errorMessageDiv.style.padding = "10px";
        errorMessageDiv.style.margin = "10px 0";
        errorMessageDiv.style.display = "none";
        errorMessageDiv.style.backgroundColor = "#ffebee";
        errorMessageDiv.style.borderRadius = "4px";
        errorMessageDiv.style.textAlign = "center";
        
        const loginBox = document.getElementById("login-box");
        if (loginBox) {
            loginBox.insertBefore(errorMessageDiv, loginBox.firstChild);
        }
    }
    
    // Add error message for email(@) elements if they donot exist
    if (!document.getElementById("email-error")) {
        const emailInput = document.getElementById("email");
        const emailErrorDiv = document.createElement("div");
        emailErrorDiv.id = "email-error";
        emailErrorDiv.className = "error-message";
        emailErrorDiv.innerText = "Please enter a valid email with @";
        emailErrorDiv.style.color = "red";
        emailErrorDiv.style.fontSize = "12px";
        emailErrorDiv.style.display = "none";
        emailInput.parentNode.insertBefore(emailErrorDiv, emailInput.nextSibling);
    }
    
    if (!document.getElementById("password-error")) {
        const passwordInput = document.getElementById("password");
        const passwordErrorDiv = document.createElement("div");
        passwordErrorDiv.id = "password-error";
        passwordErrorDiv.className = "error-message";
        passwordErrorDiv.innerText = "Password must be at least 8 characters and include special characters";
        passwordErrorDiv.style.color = "red";
        passwordErrorDiv.style.fontSize = "12px";
        passwordErrorDiv.style.display = "none";
        passwordInput.parentNode.insertBefore(passwordErrorDiv, passwordInput.nextSibling);
    }
    
    const loginBox = document.getElementById("login-box");
    if (loginBox && !document.getElementById("not-registered-error")) {
        const notRegisteredErrorDiv = document.createElement("div");
        notRegisteredErrorDiv.id = "not-registered-error";
        notRegisteredErrorDiv.className = "error-message";
        notRegisteredErrorDiv.innerText = "User not registered. Please sign up first.";
        notRegisteredErrorDiv.style.color = "red";
        notRegisteredErrorDiv.style.fontSize = "12px";
        notRegisteredErrorDiv.style.display = "none";
        loginBox.appendChild(notRegisteredErrorDiv);
    }
}

// Set up input validation for email and password
function setupInputValidation(emailInput, passwordInput) {
    // Email validation function
    function validateEmail(email) {
        const emailError = document.getElementById("email-error");
        if (!email.includes('@')) {
            if (emailError) emailError.style.display = 'block';
            return false;
        } else {
            if (emailError) emailError.style.display = 'none';
            return true;
        }
    }
    
    // Password validation function
    function validatePassword(password) {
        const passwordError = document.getElementById("password-error");
        const specialChars = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+/;
        
        if (password.length < 8 || !specialChars.test(password)) {
            if (passwordError) passwordError.style.display = 'block';
            return false;
        } else {
            if (passwordError) passwordError.style.display = 'none';
            return true;
        }
    }

    // Add event listeners to the inputs
    emailInput.addEventListener("input", function() {
        const errorDiv = document.getElementById("global-error-message");
        if (errorDiv) errorDiv.style.display = 'none';
        
        const signUpButton = document.getElementById("sign-up");
        if (signUpButton && signUpButton === document.activeElement) {
            validateEmail(this.value);
        }
    });
    
    passwordInput.addEventListener("input", function() {
        const errorDiv = document.getElementById("global-error-message");
        if (errorDiv) errorDiv.style.display = 'none';
        
        const signUpButton = document.getElementById("sign-up");
        if (signUpButton && signUpButton === document.activeElement) {
            validatePassword(this.value);
        }
    });

    // Make validation functions available globally
    window.validateEmail = validateEmail;
    window.validatePassword = validatePassword;
}

// Show global error message
function showGlobalError(message) {
    const errorDiv = document.getElementById("global-error-message");
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = "block";
    }
}

// Hide global error message
function hideGlobalError() {
    const errorDiv = document.getElementById("global-error-message");
    if (errorDiv) {
        errorDiv.style.display = "none";
    }
}

// Setup sign up button
function setupSignUpButton() {
    const signUpButton = document.getElementById("sign-up");
    if (signUpButton) {
        const originalSignUp = signUpButton.onclick;
        signUpButton.onclick = null;
        
        signUpButton.addEventListener("click", function() {
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;
            
            hideGlobalError();
            
            const isEmailValid = window.validateEmail(email);
            const isPasswordValid = window.validatePassword(password);
            
            if (!isEmailValid || !isPasswordValid) {
                return;
            }

            registeredUsers[email] = true;
            try {
                localStorage.setItem('registeredUsers', JSON.stringify(registeredUsers));
            } catch (e) {
                console.error("Error storing registered users:", e);
            }

            createUserWithEmailAndPassword(auth, email, password)
            .then((userCredential) => {
                const user = userCredential.user;

                user.getIdToken().then((token) => {
                    document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                    setupTokenRefresh(user);
                    window.location = "/";
                });
            })
            .catch((error) => {
                console.log(error.code + " " + error.message);
                
                if (error.code === "auth/email-already-in-use") {
                    showGlobalError("Email is already in use");
                } else {
                    showGlobalError("Signup error: " + error.message);
                }
            });
        });
    }
}

// Setup login button
function setupLoginButton() {
    const loginButton = document.getElementById("login");
    if (loginButton) {
        const originalLogin = loginButton.onclick;
        loginButton.onclick = null;
        
        loginButton.addEventListener("click", function() {
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;
            
            hideGlobalError();
            
            if (!email) {
                showGlobalError("Please enter your email");
                return;
            }
            
            if (!password) {
                showGlobalError("Please enter your password");
                return;
            }

            clearAuthState();

            signInWithEmailAndPassword(auth, email, password)
            .then((userCredential) => {
                // User logged in
                const user = userCredential.user;
                console.log("logged in");

                user.getIdToken().then((token) => {
                    document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                    setupTokenRefresh(user);
                    window.location = "/";
                });
            })
            .catch((error) => {
                console.log("Login error:", error.code, error.message);
                
                if (error.code === "auth/user-not-found") {
                    showGlobalError("User not found. Please check your email or sign up.");
                } else if (error.code === "auth/wrong-password") {
                    showGlobalError("Incorrect password. Please try again.");
                } else if (error.code === "auth/invalid-email") {
                    showGlobalError("Invalid email format. Please try again.");
                } else if (error.code === "auth/too-many-requests") {
                    showGlobalError("Too many failed login attempts. Please try again later.");
                } else {
                    showGlobalError("Login failed: " + error.message);
                }
            });
        });
    }
}

// Set up sign out button
function setupSignOutButton() {
    const signOutButton = document.getElementById("sign-out");
    if (signOutButton) {
        signOutButton.addEventListener("click", function() {
            if (!auth) {
                console.error("Firebase Auth is not initialized");
                return;
            }

            clearTokenRefreshInterval();
            
            signOut(auth)
            .then(() => {
                clearAuthState();
                window.location = "/";
            })
            .catch((error) => {
                console.error("Error signing out:", error);
                clearAuthState();
                window.location = "/";
            });
        });
    }
}

// Function to update UI for authenticated user
function updateUIForAuthenticatedUser(user) {
    const loginBox = document.getElementById("login-box");
    if (loginBox) {
        loginBox.hidden = true;
    }
    
    let headerBar = document.getElementById("user-header");
    if (!headerBar) {
        headerBar = document.createElement("div");
        headerBar.id = "user-header";
        headerBar.className = "header-bar";
        document.body.insertBefore(headerBar, document.body.firstChild);
        
        const userEmailDisplay = document.createElement("p");
        userEmailDisplay.id = "user-email-display";
        userEmailDisplay.className = "user-email";
        headerBar.appendChild(userEmailDisplay);
        
    
        let signOutButton = document.getElementById("sign-out");
        if (!signOutButton) {
            signOutButton = document.createElement("button");
            signOutButton.id = "sign-out";
            signOutButton.innerText = "Sign Out";
            signOutButton.className = "btn btn-danger";
            headerBar.appendChild(signOutButton);
            
        
            setupSignOutButton();
        } else {
            headerBar.appendChild(signOutButton);
        }
    } else {
        headerBar.hidden = false;
    }
    
    // Display user email
    const userEmailDisplay = document.getElementById("user-email-display");
    if (userEmailDisplay && user && user.email) {
        userEmailDisplay.innerText = user.email;
    }
    
    const welcomePage = document.getElementById("welcome-page");
    if (welcomePage) {
        welcomePage.remove();
    }
}

// Function to update UI for unauthenticated user
function updateUIForUnauthenticatedUser() {
    const loginBox = document.getElementById("login-box");
    if (loginBox) {
        loginBox.hidden = false;
    }
    
    const headerBar = document.getElementById("user-header");
    if (headerBar) {
        headerBar.hidden = true;
    }
}

// Function to parse cookie and get token
function parseCookieToken(cookie) {
    if (!cookie) return "";
    
    var strings = cookie.split(';');

    for (let i = 0; i < strings.length; i++) {
        var temp = strings[i].trim().split("=");
        if (temp[0] === "token") return temp[1];
    }
    return "";
}

document.addEventListener("DOMContentLoaded", function() {
    setupSignOutButton();
});

function heartbeatCheck() {
    const token = parseCookieToken(document.cookie);
    const headerBar = document.getElementById("user-header");
    const loginBox = document.getElementById("login-box");
    
    if (token && token.length > 0) {
        if (headerBar && headerBar.hidden) {
            console.log("Detected misaligned UI state - token exists but header is hidden");
            auth.onIdTokenChanged((user) => {
                if (user) {
                    updateUIForAuthenticatedUser(user);
                } else {
                    clearAuthState();
                }
            });
        }
    } else {
        if (loginBox && loginBox.hidden) {
            console.log("Detected misaligned UI state - no token but login box is hidden");
            updateUIForUnauthenticatedUser();
        }
    }
}

setInterval(heartbeatCheck, 30000);
