// Authentication state management
let currentUser = window.AUTH_USER || null;

export function isLoggedIn() {
    return currentUser !== null;
}

export function getCurrentUser() {
    return currentUser;
}
