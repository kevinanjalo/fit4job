/* Firebase Web app configuration for client-side Google Sign-In.
   Get these values from: Firebase console > Project settings > General >
   Your apps > Web app (</> icon) > SDK setup and configuration > Config.
   This is the PUBLIC web config, safe to expose in the browser - it is
   different from the service account key used on the server. */
// measurementId is optional (Firebase JS SDK v7.20.0 and later).
// The name FIREBASE_CONFIG is what templates/login.html reads - if you paste a
// fresh block from the console, keep this constant name.
const FIREBASE_CONFIG = {
  apiKey: "AIzaSyApRZsnhJbfxXseqw3fNA5WUcSc55gVRCM",
  authDomain: "fit4job-b87dc.firebaseapp.com",
  projectId: "fit4job-b87dc",
  storageBucket: "fit4job-b87dc.firebasestorage.app",
  messagingSenderId: "58959327062",
  appId: "1:58959327062:web:0487bd8ff5d990d86ab0f7",
  measurementId: "G-K6Y6Z9CXP7"
};

// Alias for anything still using the console's default variable name.
const firebaseConfig = FIREBASE_CONFIG;