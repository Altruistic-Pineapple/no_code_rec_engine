# User Data Collection System - Integration Guide

## Overview
Your recommendation engine now has comprehensive data collection capabilities for:
- **Collaborative Filtering**: User-item ratings and implicit feedback
- **Sequence Models**: Session tracking and temporal patterns

## New Database Tables

### 1. Enhanced UserActivity
Now tracks:
- `rating`: Explicit ratings (1-5) or implicit scores
- `duration`: Engagement time in seconds
- `session_id`: Groups activities into sessions
- `sequence_order`: Order within session
- `metadata`: Device, location, context (JSON)

### 2. UserItemRating
Explicit ratings table for collaborative filtering:
- User-item pairs with 1-5 star ratings
- Supports both explicit (user-given) and implicit (system-inferred) ratings
- One rating per user-item pair (updates on change)

### 3. WatchSession
Session tracking for sequence models:
- `session_id`: Unique session identifier
- `start_time` / `end_time`: Session boundaries
- `total_items_viewed`: Count of items in session
- Device type and metadata

## Backend API Endpoints

### Ratings API (`/ratings`)
```python
# Create or update rating
POST /ratings
{
  "user_id": "user-123",
  "mix_id": "mix-456",
  "content_id": "content-789",
  "rating": "4",  # 1-5 stars
  "rating_type": "explicit"  # or "implicit"
}

# Get user's ratings
GET /ratings/user/{user_id}

# Get ratings for content
GET /ratings/content/{content_id}

# Get rating matrix for collaborative filtering
GET /ratings/mix/{mix_id}/matrix
# Returns: {mix_id, ratings: [{user_id, content_id, rating}]}
```

### Sessions API (`/sessions`)
```python
# Start session
POST /sessions
{
  "session_id": "session_12345",
  "user_id": "user-123",
  "mix_id": "mix-456",
  "device_type": "web",
  "metadata": {"browser": "chrome", "screen_width": 1920}
}

# End session
PATCH /sessions/{session_id}
{
  "end_time": "2025-12-10T12:00:00Z",
  "total_items_viewed": "15"
}

# Get session activities (for sequence models)
GET /sessions/{session_id}/activities
# Returns ordered sequence of content_ids

# Get user's session history
GET /sessions/user/{user_id}/history
# Returns list of sessions with sequences
```

### Enhanced User Activity (`/user-activity`)
```python
# Log single activity (now with more fields)
POST /user-activity
{
  "user_id": "user-123",
  "mix_id": "mix-456",
  "content_id": "content-789",
  "event_type": "watched",  # view, click, play, watched, skip, like, rate
  "rating": "5",  # optional
  "duration": "120",  # seconds
  "session_id": "session_12345",
  "sequence_order": "3",
  "metadata": {"device": "mobile", "timezone": "PST"}
}

# Batch logging (efficient for offline sync)
POST /user-activity/batch
{
  "activities": [
    {...},  # multiple activity objects
    {...}
  ]
}
```

## Frontend Integration

### 1. Include the Analytics Tracker
```html
<script src="analytics-tracker.js"></script>
```

### 2. Initialize in Your App
```javascript
const tracker = new AnalyticsTracker("https://mixtape-edyc.onrender.com");

// When user starts viewing a mix
tracker.startSession(userId, mixId, 'web');

// Set context if needed later
tracker.setContext(userId, mixId);
```

### 3. Track User Interactions

#### Basic Event Tracking
```javascript
// Track views
tracker.trackView(contentId);

// Track clicks
tracker.trackClick(contentId);

// Track play/watch
tracker.trackPlay(contentId);

// Track completed watch with duration
tracker.trackWatched(contentId, 120); // 120 seconds

// Track skip
tracker.trackSkip(contentId, 30); // watched 30 seconds before skipping

// Track likes
tracker.trackLike(contentId);

// Track ratings (1-5 stars)
await tracker.trackRating(contentId, 5);
```

#### Content Engagement Tracking
```javascript
// For video/content players, track engagement time
const engagement = tracker.createEngagementTracker(contentId);

// When content starts playing
engagement.start();

// When user pauses
engagement.pause();

// When user resumes
engagement.resume();

// When content finishes
engagement.complete();

// When user skips
engagement.skip();
```

#### Example: Recommendation Card
```javascript
// Track when card is shown
tracker.trackView(contentId);

// Track when user clicks
card.addEventListener('click', () => {
  tracker.trackClick(contentId);
  // Navigate to content...
});

// Add star rating
ratingStars.addEventListener('change', async (e) => {
  const rating = e.target.value; // 1-5
  await tracker.trackRating(contentId, rating);
});
```

#### Example: Video Player Integration
```javascript
const videoPlayer = document.getElementById('player');
const engagement = tracker.createEngagementTracker(contentId);

videoPlayer.addEventListener('play', () => {
  engagement.start();
});

videoPlayer.addEventListener('pause', () => {
  engagement.pause();
});

videoPlayer.addEventListener('ended', () => {
  engagement.complete();
});

videoPlayer.addEventListener('seeked', (e) => {
  // If user skips ahead significantly, track as skip
  if (e.target.currentTime > videoPlayer.duration * 0.9) {
    engagement.skip();
  }
});
```

### 4. Session Management
```javascript
// Automatically handled:
// - Session ends when user leaves page
// - Activities are batched and flushed every 5 seconds
// - Critical events (ratings) are flushed immediately

// Manual session end (if needed)
tracker.endSession();
```

## Data Collection Strategy

### For Collaborative Filtering
**Goal**: Build user-item interaction matrix

**Collect**:
1. **Explicit ratings**: 1-5 star ratings
   ```javascript
   await tracker.trackRating(contentId, 5);
   ```

2. **Implicit ratings**: Convert behavior to scores
   ```javascript
   // Completed watch = high interest (5)
   tracker.trackWatched(contentId, duration);
   
   // Clicks but didn't complete = medium interest (3)
   tracker.trackClick(contentId);
   
   // Skip = low interest (1)
   tracker.trackSkip(contentId, duration);
   ```

### For Sequence Models
**Goal**: Capture sequential patterns in user behavior

**Collect**:
1. **Session-based sequences**:
   ```javascript
   // Start session
   tracker.startSession(userId, mixId);
   
   // Track each interaction in order
   tracker.trackView(contentId1); // sequence_order: 0
   tracker.trackClick(contentId1); // sequence_order: 1
   tracker.trackView(contentId2); // sequence_order: 2
   tracker.trackWatched(contentId2, 90); // sequence_order: 3
   ```

2. **Query**: Get sequences for training
   ```javascript
   // Get user's session history
   const response = await fetch(
     `${API_BASE_URL}/sessions/user/${userId}/history`
   );
   const data = await response.json();
   // data.sessions contains ordered sequences
   ```

## Database Queries for ML

### Get Rating Matrix (Collaborative Filtering)
```python
# Backend code
ratings = db.query(UserItemRating).filter(
    UserItemRating.mix_id == mix_id
).all()

# Build matrix
user_ids = list(set(r.user_id for r in ratings))
item_ids = list(set(r.content_id for r in ratings))
matrix = np.zeros((len(user_ids), len(item_ids)))

for r in ratings:
    i = user_ids.index(r.user_id)
    j = item_ids.index(r.content_id)
    matrix[i, j] = float(r.rating)
```

### Get User Sequences (Sequence Models)
```python
# Get sessions for a user
sessions = db.query(WatchSession).filter(
    WatchSession.user_id == user_id
).order_by(WatchSession.start_time).all()

# Get activities for each session
for session in sessions:
    activities = db.query(UserActivity).filter(
        UserActivity.session_id == session.session_id
    ).order_by(UserActivity.sequence_order).all()
    
    sequence = [a.content_id for a in activities if a.content_id]
    # Train sequence model on these sequences
```

## Next Steps

1. **Add tracker to frontend**: Include `analytics-tracker.js` in `index.html`

2. **Initialize on app load**: Create tracker instance with API URL

3. **Add event tracking**: Instrument your UI with tracking calls

4. **Test data collection**: 
   - Click around your app
   - Check `/user-activity/by-user/{user_id}` to see tracked events
   - Check `/sessions/user/{user_id}/history` to see sessions

5. **Build ML models**:
   - Use `/ratings/mix/{mix_id}/matrix` for collaborative filtering
   - Use `/sessions/user/{user_id}/history` for sequence models

6. **Optimize**: Adjust `flushInterval` in tracker for your traffic patterns

## Example: Full Integration in index.html

```javascript
// Initialize tracker
const tracker = new AnalyticsTracker(API_BASE_URL);

// On login/user context available
if (authState.user) {
  tracker.setContext(authState.user.id, currentMixId);
}

// When viewing recommendations
function displayRecommendations(recs) {
  tracker.startSession(authState.user.id, currentMixId);
  
  recs.forEach(rec => {
    const card = createRecommendationCard(rec);
    
    // Track view
    tracker.trackView(rec.content_id);
    
    // Track click
    card.addEventListener('click', () => {
      tracker.trackClick(rec.content_id);
    });
    
    // Add rating stars
    card.querySelector('.rating').addEventListener('change', async (e) => {
      await tracker.trackRating(rec.content_id, e.target.value);
    });
  });
}

// Before user leaves
window.addEventListener('beforeunload', () => {
  tracker.endSession();
});
```

## Benefits

✅ **Collaborative Filtering Ready**: User-item rating matrix for similarity-based recommendations

✅ **Sequence Model Ready**: Temporal patterns and sequential behavior tracking

✅ **Implicit + Explicit Feedback**: Both user ratings and behavioral signals

✅ **Session Context**: Group interactions into meaningful sessions

✅ **Efficient Batching**: Auto-batched API calls reduce server load

✅ **Metadata Rich**: Device, timing, and context for advanced models
