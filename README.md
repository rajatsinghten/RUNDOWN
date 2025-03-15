# RunDown - Smart Task Management System

## 📋 Overview

RunDown is an AI-powered task management system that seamlessly integrates with your Gmail and Google Calendar to automatically extract important tasks and events from your emails. The application uses Google's Generative AI to intelligently identify actionable items in your inbox and presents them as suggested tasks that can be easily added to your to-do list and calendar with a single click.

## ✨ Features

- **Smart Email Processing**: Automatically scans your Gmail for potential tasks and events
- **AI-Powered Task Extraction**: Uses Google's Generative AI to identify actionable items in emails
- **Interest-Based Filtering**: Customizable preferences to only show task suggestions relevant to your interests
- **Time Period Filtering**: Filter suggested tasks based on email time periods (last 24 hours, 7 days, 15 days, or 30 days)
- **Two-Way Calendar Sync**: Tasks added to your to-do list are automatically synced with Google Calendar (and vice versa)
- **Smart Date Detection**: Accurately extracts event dates mentioned in emails
- **Intelligent Reminders**: Sets appropriate reminders for upcoming events (24h before and 30min before)
- **Natural Language Task Entry**: Add tasks using natural language with automatic date extraction
- **Smart Scheduling Assistant**: Ask about your availability, get suggestions for free time slots, and schedule events
- **User Preferences**: Customize your experience with personalized interest categories
- **Secure Authentication**: OAuth integration with Google for secure access to your data
- **Intelligent Chatbot**: AI-powered chatbot that understands commands to add and remove events

## 🛠️ Technology Stack

- **Backend**: Python Flask
- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Authentication**: Google OAuth
- **Data Storage**: File-based storage (JSON)
- **AI Integration**: Google Generative AI (Gemini 1.5 Flash)
- **Google API Integration**: Gmail API, Google Calendar API

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- A Google Cloud Platform account with Gmail and Calendar APIs enabled
- Google API credentials (OAuth client ID and client secret)
- Google Generative AI API key

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/rundown.git
   cd rundown
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up configuration files**:
   - Create a `.env` file with your Google API key:
     ```
     GOOGLE_API_KEY=your_generative_ai_api_key
     ```
   - Place your `credentials.json` file (obtained from Google Cloud Console) in the project root

5. **Create required directories**:
   ```bash
   mkdir -p tokens
   ```

6. **Run the application**:
   ```bash
   python app.py
   ```

7. **Access the application**:
   Open your browser and navigate to `http://127.0.0.1:5000`

## ⚙️ Configuration

### config.py

The main configuration file contains various settings for the application:

```python
# Example config.py
SECRET_KEY = "your-secret-key"
TOKENS_DIR = "tokens"
LABEL_NAME = "RunDown-Processed"
GOOGLE_API_KEY = "your-google-api-key"  # Overridden by .env file if present
```

### credentials.json

This file contains your OAuth client credentials. Obtain this from Google Cloud Console:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable Gmail API and Google Calendar API
4. Create OAuth credentials
5. Download the credentials JSON file and rename it to `credentials.json`

## 🔌 Integration Setup

### Enable Required Google APIs

1. **Gmail API**: For accessing and processing emails
2. **Google Calendar API**: For creating and managing calendar events
3. **Google OAuth**: For user authentication

### Configure OAuth Consent Screen

1. Set up the OAuth consent screen in Google Cloud Console
2. Add the following scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/calendar.events`

## 🧩 Project Structure

```
RunDown/
├── app.py                # Main application file
├── config.py             # Configuration settings
├── credentials.json      # Google OAuth credentials
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables
├── .gitignore            # Git ignore file
├── static/               # Static files
│   ├── css/              # CSS stylesheets
│   └── js/               # JavaScript files
├── templates/            # HTML templates
│   ├── chat.html         # Main application interface
│   ├── login.html        # Login page
│   ├── preferences.html  # User preferences page
│   └── error.html        # Error page
├── routes/               # Route handlers
│   ├── auth_routes.py    # Authentication routes
│   ├── calendar_routes.py # Calendar-related routes
│   ├── chat_routes.py    # Chat functionality routes
│   ├── gmail_routes.py   # Gmail integration routes
│   └── preferences_routes.py # User preferences routes
├── utils/                # Utility functions
│   ├── auth.py           # Authentication utilities
│   ├── calendar.py       # Calendar utilities
│   ├── gmail.py          # Gmail utilities
│   └── models.py         # Data models
└── tokens/               # Token storage directory
```

## 🔄 Application Flow

1. **Authentication**: Users authenticate with their Google account
2. **Preferences Selection**: First-time users select their interests
3. **Email Processing**: The system processes emails in the background looking for tasks/events
4. **Task Suggestions**: Relevant task suggestions are displayed based on user preferences
5. **Task Management**: Users can add suggested tasks to their to-do list or create new tasks manually
6. **Calendar Integration**: Tasks are automatically synced with Google Calendar
7. **AI Assistant**: Users can ask questions about their schedule or tasks

## 📱 Usage Guide

### Authentication

1. Visit the application URL
2. Click "Continue with Google"
3. Grant the required permissions

### Setting Preferences

1. After first login, you'll be directed to the preferences page
2. Select interests relevant to you (e.g., Internships, Hackathons, Cultural Events)
3. Add custom interests if needed
4. Save your preferences

### Managing Tasks

1. **View Suggested Tasks**: Click the "Tasks" button to see AI-generated task suggestions
2. **Filter Suggestions by Time Period**: Use the dropdown to view emails from the last 24 hours, 7 days, 15 days, or 30 days
3. **Add Suggested Task**: Click "Add to Task List" on any suggestion
4. **Create Manual Task**: Type a task in the input field and click "Add"
5. **Set Task Deadline**: Use the date picker to set a deadline for manual tasks
6. **Track Task Status**: Change task status using the dropdown (Not Started, In Progress, Completed)
7. **Delete Tasks**: Click the delete button to remove tasks from both the to-do list and calendar

### AI Assistant

1. Click the "Chats" button to open the AI assistant
2. Ask questions about your schedule, tasks, or emails
3. Use command prefixes for specific actions:
   - **@add**: Create a new event (e.g., "@add Meeting with John tomorrow at 3pm")
   - **@remove**: Delete an event (e.g., "@remove Project meeting")
   - **@list**: View upcoming events on your calendar
   - **@check**: Check your availability on a specific day (e.g., "@check tomorrow")
   - **@when**: Ask when you're free on a specific day (e.g., "@when am I free on Friday?")
   - **@suggest**: Get suggestions for optimal meeting times based on your calendar (e.g., "@suggest time for team dinner next week")
   - **@help**: Get information about available commands
4. Receive intelligent responses based on your data
5. Confirm scheduling suggestions with simple yes/no responses to add events to your calendar

## 🔄 API Endpoints

### Authentication

- `GET /login`: Initiates the Google OAuth flow
- `GET /oauth/callback`: OAuth callback handler
- `GET /logout`: Logs out the current user
- `GET /auth/status`: Checks authentication status
- `GET /api/session`: Verifies session status

### Task Management

- `POST /addtask`: Adds a task to the to-do list and calendar
- `POST /addsuggestion`: Gets task suggestions from emails

### Calendar Integration

- `GET /calendar`: Fetches calendar events
- `POST /calendar/delete`: Deletes a calendar event

### Email Integration

- `GET /gmail`: Fetches emails from Gmail

### User Preferences

- `GET /preferences`: Renders the preferences page
- `GET /api/preferences`: Gets user preferences
- `POST /api/preferences`: Updates user preferences

## 🔍 Advanced Features

### Interest-Based Filtering

The system filters email suggestions based on your selected interests. For example, if you're interested in "Hackathons" and "Internships", only emails related to these topics will generate task suggestions.

### Smart Date Extraction

RunDown uses AI to extract specific dates and times mentioned in emails. For example, if an email mentions "Meeting on March 22nd at 10:30 AM", the system will create the calendar event at that exact date and time.

### Calendar Integration

Tasks in RunDown are automatically synchronized with Google Calendar:
- Adding a task creates a calendar event
- Deleting a task removes the corresponding calendar event
- Events include reminders (24 hours before and 30 minutes before)

### Email Processing

The system scans your inbox for actionable emails and:
1. Analyzes the content to determine if it contains tasks or events
2. Extracts relevant information like dates, times, and locations
3. Creates task suggestions based on this information
4. Marks processed emails with a special label to avoid duplication

### Smart Duplicate Prevention

RunDown uses multiple strategies to prevent duplicate tasks:

1. **Email ID Tracking**: Stores email IDs when creating tasks from emails to prevent re-suggesting the same email
2. **Event ID Comparison**: Checks calendar event IDs to avoid duplicate entries
3. **Text Matching**: Compares task text to prevent similar tasks from being added multiple times
4. **Cross-Interface Deduplication**: Tasks added via the chatbot won't appear in suggestions and vice versa

### AI Chatbot Commands

The built-in AI chatbot supports command prefixes for quick task management:

- **@add [event details]**: Creates a new calendar event and adds it to your task list
  - Extracts dates, times, and locations from your description
  - Uses natural language processing to understand relative dates (tomorrow, next week, etc.)
  - Defaults to appropriate times if not specified
  
- **@remove [event name]**: Deletes an event from your calendar and task list
  - Finds the best matching event based on your description
  - Confirms successful deletion

- **@list**: Shows your upcoming calendar events
  - Displays events in chronological order
  - Includes date, time, and location information

- **@check [date]**: Checks your availability on a specific date
  - Shows all booked events for that day
  - Lists available time slots for scheduling
  - Works with natural language date references ("next Monday", "tomorrow", etc.)

- **@when [query]**: Finds times when you're available for an event
  - Analyzes your calendar for the specified day
  - Shows all free time slots
  - Works with queries like "When am I free tomorrow?"

- **@suggest [event details]**: Suggests optimal times for scheduling events
  - Analyzes your calendar to find suitable free time slots
  - Considers event duration and time preferences (morning, afternoon, etc.)
  - Offers to add the event to your calendar with a simple confirmation
  - Example: "@suggest time for a 1-hour coffee meeting tomorrow afternoon"

- **@help**: Provides information on available commands
  - Shows detailed usage examples
  - Offers tips for effective command usage

## 🔧 Troubleshooting

### Authentication Issues

- **Error 401/403**: Clear your browser cookies and try logging in again
- **OAuth Error**: Verify that your credentials.json file is correct and OAuth consent screen is configured properly

### Calendar Event Timing Issues

- **Wrong Event Times**: The system may sometimes misinterpret dates or times. Manually adjust the event in Google Calendar if needed.
- **Default 9 AM Events**: If events are consistently created at 9 AM despite having specific times in emails, check the console logs for date parsing errors.

### Email Processing Issues

- **Missing Suggestions**: Verify your interest preferences to ensure they match the email content
- **Duplicate Suggestions**: The system should avoid showing already processed emails, but occasionally duplicates may appear

## 📈 Future Enhancements

- Mobile application support
- Integration with other email providers
- Advanced natural language processing for better task extraction
- Team collaboration features
- Cloud-based deployment
- Database storage instead of file-based storage
- Enhanced analytics and reporting

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.

---

© 2023 RunDown. All rights reserved.