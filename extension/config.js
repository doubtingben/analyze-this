// Configuration
const CONFIG = {
    //API_BASE_URL: "http://localhost:8000" // Dev
    API_BASE_URL: "https://interestedparticipant.org" // Prod
};

// Make it available to module-less scripts if needed or just global
if (typeof window !== 'undefined') {
    window.CONFIG = CONFIG;
}
