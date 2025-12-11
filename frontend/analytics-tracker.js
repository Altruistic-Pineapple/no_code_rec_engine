/**
 * Analytics Tracker for User Behavior Collection
 * Captures interactions for collaborative filtering and sequence models
 */

class AnalyticsTracker {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
        this.sessionId = this.generateSessionId();
        this.sequenceCounter = 0;
        this.activityQueue = [];
        this.flushInterval = 5000; // Flush every 5 seconds
        this.sessionStartTime = Date.now();
        this.currentMixId = null;
        this.currentUserId = null;
        
        // Start auto-flush timer
        this.startAutoFlush();
        
        // Track page visibility for session management
        this.setupVisibilityTracking();
    }
    
    generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    setContext(userId, mixId) {
        this.currentUserId = userId;
        this.currentMixId = mixId;
    }
    
    async startSession(userId, mixId, deviceType = 'web') {
        this.currentUserId = userId;
        this.currentMixId = mixId;
        this.sessionId = this.generateSessionId();
        this.sequenceCounter = 0;
        this.sessionStartTime = Date.now();
        
        try {
            await fetch(`${this.apiBaseUrl}/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    user_id: userId,
                    mix_id: mixId,
                    device_type: deviceType,
                    metadata: {
                        user_agent: navigator.userAgent,
                        screen_width: window.screen.width,
                        screen_height: window.screen.height,
                        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
                    }
                })
            });
        } catch (error) {
            console.error('Failed to start session:', error);
        }
    }
    
    async endSession() {
        if (!this.sessionId) return;
        
        // Flush any pending activities
        await this.flush();
        
        try {
            await fetch(`${this.apiBaseUrl}/sessions/${this.sessionId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    end_time: new Date().toISOString(),
                    total_items_viewed: String(this.sequenceCounter)
                })
            });
        } catch (error) {
            console.error('Failed to end session:', error);
        }
    }
    
    trackEvent(eventType, contentId = null, additionalData = {}) {
        if (!this.currentUserId || !this.currentMixId) {
            console.warn('Cannot track event: user or mix context not set');
            return;
        }
        
        const activity = {
            user_id: this.currentUserId,
            mix_id: this.currentMixId,
            content_id: contentId,
            event_type: eventType,
            session_id: this.sessionId,
            sequence_order: String(this.sequenceCounter++),
            ...additionalData
        };
        
        this.activityQueue.push(activity);
        
        // Flush immediately for critical events
        if (['rate', 'purchase', 'share'].includes(eventType)) {
            this.flush();
        }
    }
    
    trackView(contentId, duration = null) {
        this.trackEvent('view', contentId, { 
            duration: duration ? String(duration) : null 
        });
    }
    
    trackClick(contentId) {
        this.trackEvent('click', contentId);
    }
    
    trackPlay(contentId) {
        this.trackEvent('play', contentId);
    }
    
    trackWatched(contentId, duration) {
        this.trackEvent('watched', contentId, { 
            duration: String(duration) 
        });
    }
    
    trackSkip(contentId, duration) {
        this.trackEvent('skip', contentId, { 
            duration: String(duration) 
        });
    }
    
    trackLike(contentId) {
        this.trackEvent('like', contentId);
    }
    
    async trackRating(contentId, rating) {
        // Log to activity
        this.trackEvent('rate', contentId, { 
            rating: String(rating) 
        });
        
        // Also create explicit rating record
        try {
            await fetch(`${this.apiBaseUrl}/ratings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.currentUserId,
                    mix_id: this.currentMixId,
                    content_id: contentId,
                    rating: String(rating),
                    rating_type: 'explicit'
                })
            });
        } catch (error) {
            console.error('Failed to save rating:', error);
        }
    }
    
    async flush() {
        if (this.activityQueue.length === 0) return;
        
        const activities = [...this.activityQueue];
        this.activityQueue = [];
        
        try {
            await fetch(`${this.apiBaseUrl}/user-activity/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ activities })
            });
        } catch (error) {
            console.error('Failed to flush activities:', error);
            // Re-queue if failed
            this.activityQueue.unshift(...activities);
        }
    }
    
    startAutoFlush() {
        setInterval(() => {
            this.flush();
        }, this.flushInterval);
    }
    
    setupVisibilityTracking() {
        // End session when user leaves
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.endSession();
            }
        });
        
        // Also flush on page unload
        window.addEventListener('beforeunload', () => {
            this.flush();
        });
    }
    
    // Content engagement tracker with time measurement
    createEngagementTracker(contentId) {
        let startTime = Date.now();
        let isEngaged = true;
        
        return {
            start: () => {
                startTime = Date.now();
                isEngaged = true;
            },
            pause: () => {
                if (isEngaged) {
                    const duration = Math.floor((Date.now() - startTime) / 1000);
                    this.trackEvent('pause', contentId, { 
                        duration: String(duration) 
                    });
                    isEngaged = false;
                }
            },
            resume: () => {
                startTime = Date.now();
                isEngaged = true;
            },
            complete: () => {
                const duration = Math.floor((Date.now() - startTime) / 1000);
                this.trackWatched(contentId, duration);
            },
            skip: () => {
                const duration = Math.floor((Date.now() - startTime) / 1000);
                this.trackSkip(contentId, duration);
            }
        };
    }
}

// Export for use in main app
window.AnalyticsTracker = AnalyticsTracker;
