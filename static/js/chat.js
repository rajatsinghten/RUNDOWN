// Add this at the beginning of the file to check session before proceeding
async function checkSession() {
  try {
    const response = await fetch('/api/session', {
      method: 'GET',
      credentials: 'include'
    });
    
    const data = await response.json();
    
    if (!response.ok || !data.authenticated) {
      console.log('Session not valid, redirecting to login page');
      window.location.href = data.redirect || '/login';
      return false;
    }
    
    return true;
  } catch (error) {
    console.error('Error checking session:', error);
    // If there's an error checking the session, assume we need to login
    window.location.href = '/login';
    return false;
  }
}

// Handle API responses and check for auth issues
function handleApiResponse(response) {
  if (response.status === 401 || response.status === 403) {
    // Auth error
    return response.json().then(data => {
      if (data.redirect) {
        console.log('Authentication required, redirecting to:', data.redirect);
        window.location.href = data.redirect;
      } else {
        console.log('Authentication error, redirecting to login');
        window.location.href = '/login';
      }
      throw new Error('Authentication required');
    });
  }
  
  if (!response.ok) {
    return response.json().then(data => {
      throw new Error(data.error || 'API request failed');
    });
  }
  
  return response.json();
}

// Panel Management

function setupPanel(triggerId, panelId) {
  const trigger = document.getElementById(triggerId);
  const panel = document.getElementById(panelId);
  const closeBtn = panel.querySelector('.close-panel-btn');

  const togglePanel = () => {
      const isExpanding = !panel.classList.contains('expanded');
      panel.classList.toggle('expanded');
      trigger.style.display = isExpanding ? 'none' : 'block';
  };

  trigger.addEventListener('click', togglePanel);
  closeBtn.addEventListener('click', togglePanel);
}

// Error handling and notification
function showNotification(message, type = 'info') {
  // Create notification element if it doesn't exist
  let notification = document.getElementById('notification');
  if (!notification) {
    notification = document.createElement('div');
    notification.id = 'notification';
    document.body.appendChild(notification);
  }
  
  // Set appropriate class based on type
  notification.className = `notification ${type}`;
  notification.textContent = message;
  
  // Show notification
  notification.style.display = 'block';
  
  // Hide after 5 seconds
  setTimeout(() => {
    notification.style.display = 'none';
  }, 5000);
}

// Task Management
const taskInput = document.getElementById('taskInput');
const taskDeadline = document.getElementById('taskDeadline');
const addTaskBtn = document.getElementById('addTaskBtn');
const taskList = document.getElementById('taskList');
const suggestionBox = document.getElementById('suggestedList');
const datePickerBtn = document.getElementById('date-picker-btn');

// Add event listener for the date picker button
datePickerBtn.addEventListener('click', () => {
  taskDeadline.showPicker();
});

function addTask(taskValue, deadline, eventUrl = null, eventId = null, emailId = null) {
  console.log(`Adding task to todo list: "${taskValue}", deadline: ${deadline}, eventUrl: ${eventUrl}, eventId: ${eventId}, emailId: ${emailId}`);
  
  // Check if this task already exists by ID or text
  if (isDuplicateTask(taskValue, eventId, emailId)) {
    console.log(`Task "${taskValue}" appears to be a duplicate, not adding`);
    showNotification("This task already exists in your list", "info");
    return false;
  }
  
  const taskItem = document.createElement("li");
  taskItem.className = "task-item";
  
  // Store event ID and email ID as data attributes if available
  if (eventId) {
    taskItem.dataset.eventId = eventId;
  }
  
  if (emailId) {
    taskItem.dataset.emailId = emailId;
  }
  
  taskItem.innerHTML = `
      <div class="task-content">
          <div class="status-indicator status-not-started"></div>
          <div>
              <span class="task-text">${taskValue}</span>
              ${deadline ? `<div class="task-deadline"> ${deadline}</div>` : ''}
              ${eventUrl ? `<a href="${eventUrl}" target="_blank" class="event-link">Calendar Event</a>` : ''}
          </div>
      </div>
      <div class="task-controls">
          <select class="status-select">
              <option value="not-started">Not Started</option>
              <option value="in-progress">In Progress</option>
              <option value="completed">Completed</option>
          </select>
          <button class="delete-btn">Delete</button>
      </div>
  `;
  taskList.appendChild(taskItem);
  
  // Log the current task list for debugging
  console.log(`Task list now has ${taskList.children.length} items`);
  return true;
}

function isDuplicateTask(taskText, eventId = null, emailId = null) {
  // First check existing event IDs if provided
  if (eventId) {
    const existingItem = document.querySelector(`.task-item[data-event-id="${eventId}"]`);
    if (existingItem) return true;
  }
  
  // Then check email IDs if provided
  if (emailId) {
    const existingItem = document.querySelector(`.task-item[data-email-id="${emailId}"]`);
    if (existingItem) return true;
  }
  
  // Finally check by task text
  const existingTaskTexts = Array.from(taskList.querySelectorAll('.task-text'))
    .map(el => el.textContent.toLowerCase().trim());
  return existingTaskTexts.includes(taskText.toLowerCase().trim());
}

addTaskBtn.addEventListener('click', async () => {
  const taskText = taskInput.value.trim();
  const deadline = taskDeadline.value;
  
  if (!taskText) {
      showInputError('Please enter a task!');
      return;
  }

  // Check if this task already exists
  if (isDuplicateTask(taskText)) {
    showNotification('This task already exists in your list!', 'error');
    return;
  }

  try {
    // Format deadline for sending to API
    let formattedDeadline = '';
    if (deadline) {
      formattedDeadline = new Date(deadline).toISOString();
    }
    
    // Add to calendar via API
    const response = await fetch("/addtask", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({
        task_text: taskText,
        event_date: formattedDeadline,
        display_date: deadline ? new Date(deadline).toLocaleString() : ''
      }),
      credentials: "include"
    });

    try {
      const data = await handleApiResponse(response);
      
      // Extract event ID from URL if available
      let eventId = null;
      if (data.event) {
        eventId = extractEventIdFromUrl(data.event);
        if (eventId) {
          console.log(`Added task with calendar event ID: ${eventId}`);
          
          // Add to current event IDs
          const currentEventIds = JSON.parse(localStorage.getItem('currentEventIds') || '[]');
          if (!currentEventIds.includes(eventId)) {
            currentEventIds.push(eventId);
            localStorage.setItem('currentEventIds', JSON.stringify(currentEventIds));
          }
        }
      }
      
      // Add to UI with formatted deadline
      const displayDeadline = data.deadline || (deadline ? new Date(deadline).toLocaleString() : '');
      addTask(data.response || taskText, displayDeadline, data.event, eventId, data.email_id);
      
      showNotification('Task added successfully!', 'success');
      
      taskInput.value = '';
      taskDeadline.value = '';
      taskInput.focus();
    } catch (error) {
      if (error.message === 'Authentication required') {
        // This will be handled by handleApiResponse
        return;
      }
      throw error;
    }
  } catch (error) {
    console.error("Error adding task:", error);
    showNotification(`Error: ${error.message}`, 'error');
    // Fallback to local-only task if API call fails
    const displayDeadline = deadline ? new Date(deadline).toLocaleString() : '';
    addTask(taskText, displayDeadline);
    taskInput.value = '';
    taskDeadline.value = '';
  }
});

taskInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') addTaskBtn.click();
});

// Chat Interface
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');

function addMessage(message, isUser = true, isMarkdown = false) {
  const div = document.createElement('div');
  div.className = `chat-message ${isUser ? 'user-message' : 'bot-message'}`;
  
  // Handle markdown formatting if enabled
  if (isMarkdown && !isUser) {
    // Basic markdown processing for bold, italics, links
    let formattedMessage = message
      // Handle bold text: **text** -> <strong>text</strong>
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      // Handle italic text: *text* -> <em>text</em>
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      // Handle links: [text](url) -> <a href="url">text</a>
      .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>')
      // Handle inline code: `code` -> <code>code</code>
      .replace(/`(.*?)`/g, '<code>$1</code>')
      // Handle line breaks
      .replace(/\n/g, '<br>');
    
    div.innerHTML = formattedMessage;
  } else {
    div.textContent = message;
  }
  
  // Get the chat messages container
  const chatMessages = document.getElementById('chat-messages');
  if (!chatMessages) {
    console.error("Chat messages container not found");
    return;
  }
  
  // Check if user was already at the bottom before adding message
  const wasAtBottom = chatMessages.scrollHeight - chatMessages.clientHeight <= chatMessages.scrollTop + 50;
  
  // Add the message
  chatMessages.appendChild(div);
  
  // If user was at the bottom, scroll to the new bottom
  if (wasAtBottom) {
    setTimeout(() => {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 10);
  }
}

function showCommandSuggestions() {
  const commandList = document.createElement('div');
  commandList.className = 'command-suggestions';
  commandList.innerHTML = `
    <div class="command-suggestion" data-command="@add ">Add Event</div>
    <div class="command-suggestion" data-command="@remove ">Remove Event</div>
    <div class="command-suggestion" data-command="@list">List Events</div>
    <div class="command-suggestion" data-command="@help">Help</div>
  `;
  
  // Add click handlers
  commandList.querySelectorAll('.command-suggestion').forEach(btn => {
    btn.addEventListener('click', () => {
      userInput.value = btn.dataset.command;
      userInput.focus();
      commandList.remove();
    });
  });
  
  // Add to chat container
  const inputContainer = userInput.closest('.input-container');
  inputContainer.parentNode.insertBefore(commandList, inputContainer);
  
  // Auto-hide after 15 seconds
  setTimeout(() => {
    if (document.body.contains(commandList)) {
      commandList.remove();
    }
  }, 15000);
}

async function sendMessage() {
  // Get the message from the input
  const message = userInput.value.trim();
  if (message === "") return;

  // Add the user message to the UI
  addMessage(message, true);
  userInput.value = '';

  // Check if this is a follow-up to a suggestion
  const isFollowUp = localStorage.getItem('awaitingFollowUp') === 'true';
  let followUpAction = '';

  if (isFollowUp) {
    // Clear the follow-up flag
    localStorage.removeItem('awaitingFollowUp');
    localStorage.removeItem('suggestedEventData');
    
    // Check if the response is positive
    const positiveResponses = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'add it', 'add', 'create', 'schedule', 'confirm'];
    const isPositive = positiveResponses.some(response => message.toLowerCase().includes(response));
    
    if (isPositive) {
      followUpAction = 'add_event';
    }
  }

  try {
    // Show loading indicator
    const loadingMessage = addMessage("...", false);
    
    const requestData = { message };
    
    // If this is a follow-up, add the necessary data
    if (followUpAction === 'add_event') {
      requestData.follow_up = true;
      requestData.action = 'add_event';
    }
    
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify(requestData),
      credentials: "include"
    });

    try {
      const data = await handleApiResponse(response);
      
      // Check if this was a command response (for special formatting)
      const isCommand = data.command_detected === true;
      const useMarkdown = isCommand || data.markdown === true;
      
      // Remove loading message
      if (loadingMessage) {
        loadingMessage.remove();
      }
      
      addMessage(data.response, false, useMarkdown);
      
      // Handle event suggestions that need follow-up
      if (data.ask_followup && data.event_suggestion) {
        // Store that we're awaiting a follow-up
        localStorage.setItem('awaitingFollowUp', 'true');
        localStorage.setItem('suggestedEventData', JSON.stringify(data.event_suggestion));
        
        // Add quick response buttons for yes/no
        addFollowUpButtons();
      }
      
      // Special handling for event data from commands
      if (isCommand && data.event_data) {
        // If this is an @add command, add the task to the todo list
        if (data.event_data.title && data.event_data.datetime) {
          console.log("Adding task to todo list from chatbot command:", data.event_data);
          
          // Extract event ID from URL if available
          let eventId = null;
          if (data.event_data.event_id) {
            eventId = data.event_data.event_id;
          } else if (data.event_data.link) {
            eventId = extractEventIdFromUrl(data.event_data.link);
          }
          
          // Add to todo list UI
          const addedTask = addTask(
            data.event_data.title, 
            data.event_data.datetime, 
            data.event_data.link, 
            eventId,
            data.event_data.email_id
          );
          
          if (addedTask) {
            showNotification(`Added "${data.event_data.title}" to your task list`, "success");
          }
          
          // Add to current event IDs for tracking
          if (eventId) {
            const currentEventIds = JSON.parse(localStorage.getItem('currentEventIds') || '[]');
            if (!currentEventIds.includes(eventId)) {
              currentEventIds.push(eventId);
              localStorage.setItem('currentEventIds', JSON.stringify(currentEventIds));
            }
          }
          
          // Add email ID to the list of processed emails
          if (data.event_data.email_id) {
            const processedEmailIds = JSON.parse(localStorage.getItem('processedEmailIds') || '[]');
            if (!processedEmailIds.includes(data.event_data.email_id)) {
              processedEmailIds.push(data.event_data.email_id);
              localStorage.setItem('processedEmailIds', JSON.stringify(processedEmailIds));
            }
          }
        }
      }
      
      // Show command suggestions to new users
      if (message.toLowerCase() === "hi" || 
          message.toLowerCase() === "hello" || 
          message.toLowerCase() === "hey") {
        setTimeout(() => {
          addMessage("Would you like to try one of these commands?", false);
          showCommandSuggestions();
        }, 500);
      }
    } catch (error) {
      if (error.message === 'Authentication required') {
        // This will be handled by handleApiResponse
        return;
      }
      throw error;
    }
  } catch (error) {
    console.error("Error:", error);
    addMessage("Sorry, there was an error processing your request.", false);
  }
}

// Function to add follow-up buttons for easier responses
function addFollowUpButtons() {
  const buttonsContainer = document.createElement('div');
  buttonsContainer.className = 'followup-buttons';
  buttonsContainer.innerHTML = `
    <button class="followup-btn yes-btn">Yes, add it</button>
    <button class="followup-btn no-btn">No, thanks</button>
  `;
  
  // Add to chat messages
  document.getElementById('chat-messages').appendChild(buttonsContainer);
  
  // Add event listeners
  buttonsContainer.querySelector('.yes-btn').addEventListener('click', () => {
    userInput.value = "Yes, please add it to my calendar";
    sendMessage();
    buttonsContainer.remove();
  });
  
  buttonsContainer.querySelector('.no-btn').addEventListener('click', () => {
    userInput.value = "No, thank you";
    sendMessage();
    buttonsContainer.remove();
  });
  
  // Add styles for the buttons
  const style = document.createElement('style');
  style.textContent = `
    .followup-buttons {
      display: flex;
      gap: 10px;
      margin: 10px 0;
    }
    .followup-btn {
      padding: 8px 16px;
      border-radius: 20px;
      border: none;
      cursor: pointer;
      font-weight: bold;
      transition: all 0.2s;
    }
    .yes-btn {
      background-color: #4caf50;
      color: white;
    }
    .no-btn {
      background-color: #f44336;
      color: white;
    }
    .followup-btn:hover {
      opacity: 0.9;
      transform: translateY(-2px);
    }
  `;
  document.head.appendChild(style);
}

// Helper function to extract event ID from Google Calendar URL
function extractEventIdFromUrl(url) {
  if (!url) return null;
  
  // Handle different formats of Google Calendar URLs
  const patterns = [
    /\/events\/([^/]+)/,  // Standard format
    /eid=([^&]+)/,        // Another possible format
    /calendar\/event\?eid=([^&]+)/  // Yet another format
  ];
  
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }
  
  return null;
}

// Load calendar events as tasks
async function loadCalendarEvents() {
  try {
    const response = await fetch("/calendar", {
      method: "GET",
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: "include"
    });
    
    try {
      const data = await handleApiResponse(response);
      
      if (data.events && data.events.length > 0) {
        // Clear existing tasks first
        taskList.innerHTML = '';
        
        // Track all event IDs
        const eventIds = [];
        
        // Add calendar events as tasks
        data.events.forEach(event => {
          const title = event.summary;
          const start = event.start && event.start.dateTime ? new Date(event.start.dateTime).toLocaleString() : null;
          console.log(`Loading calendar event: ${title}, ID: ${event.id}`);
          
          if (event.id) {
            eventIds.push(event.id);
          }
          
          addTask(title, start, event.htmlLink, event.id, event.email_id);
        });
        
        // Store the event IDs in localStorage for comparison with suggestions
        localStorage.setItem('currentEventIds', JSON.stringify(eventIds));
      }
    } catch (error) {
      if (error.message === 'Authentication required') {
        // This will be handled by handleApiResponse
        return;
      }
      throw error;
    }
  } catch (error) {
    console.error("Error loading calendar events:", error);
    showNotification(`Error loading events: ${error.message}`, 'error');
  }
}

// Suggestions Functionality
function addSuggestion(suggestion) {
  if (!suggestion || !suggestion.text) return;
  
  // Log all suggestion data for debugging
  console.log("Adding suggestion with data:", JSON.stringify(suggestion));
  
  const urgencyClass = suggestion.is_time_sensitive ? 'urgent-suggestion' : '';
  const emailLink = suggestion.email_id ? 
    `<a href="https://mail.google.com/mail/u/0/#inbox/${suggestion.email_id}" class="email-link" target="_blank">📧 View Email</a>` : '';
  
  // Add location if available
  const locationDisplay = suggestion.location ? 
    `<p class="location">📍 ${suggestion.location}</p>` : '';
  
  const div = document.createElement('div');
  div.innerHTML = `
      <div class="suggested-item ${urgencyClass}">
          <p class="text">${suggestion.text}</p>
          ${suggestion.deadline ? `<p class="deadline">📅 ${suggestion.deadline}</p>` : ''}
          ${locationDisplay}
          ${emailLink}
          <div class="suggestion-actions">
            <button class="btn add-btn">Add to Task List</button>
            <button class="btn delete-btn">Dismiss</button>
          </div>
      </div>`;
  
  // Store original event_date as a data attribute if available
  const suggestedItem = div.querySelector('.suggested-item');
  
  // Check both event_date fields to cover all bases
  const eventDate = suggestion.event_date || '';
  if (eventDate) {
    suggestedItem.dataset.eventDate = eventDate;
    console.log(`Stored original event_date in suggestion DOM: ${eventDate}`);
  }
  
  // Also store the raw deadline date if available
  if (suggestion.deadline) {
    suggestedItem.dataset.deadline = suggestion.deadline;
    console.log(`Stored deadline in suggestion DOM: ${suggestion.deadline}`);
  }
  
  suggestionBox.appendChild(div);
}

async function getSuggestions() {
  // First, check if the filter dropdown exists, if not, create it
  let filterContainer = document.querySelector('.filter-container');
  
  if (!filterContainer) {
    filterContainer = document.createElement('div');
    filterContainer.className = 'filter-container';
    filterContainer.innerHTML = `
      <label for="time-period-filter">Show emails from:</label>
      <select id="time-period-filter" class="filter-dropdown">
        <option value="1">Last 24 hours</option>
        <option value="7" selected>Last 7 days</option>
        <option value="15">Last 15 days</option>
        <option value="30">Last 30 days</option>
      </select>
    `;
    suggestionBox.parentNode.insertBefore(filterContainer, suggestionBox);
    
    // Add event listener to reload suggestions when the filter changes
    document.getElementById('time-period-filter').addEventListener('change', getSuggestions);
  }
  
  // Get the selected time period
  const timePeriod = document.getElementById('time-period-filter').value;
  
  suggestionBox.innerHTML = '<div class="loading">Loading suggestions...</div>';
  try {
    const response = await fetch("/addsuggestion", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({ time_period: timePeriod }),
      credentials: "include"
    });

    try {
      const data = await handleApiResponse(response);
      
      // Clear the suggestions
      suggestionBox.innerHTML = '';
      
      if (data.suggestions?.length) {
        // Get currently displayed tasks and deleted events
        const currentEventIds = JSON.parse(localStorage.getItem('currentEventIds') || '[]');
        const deletedEventIds = JSON.parse(localStorage.getItem('deletedEventIds') || '[]');
        const existingTaskTexts = Array.from(taskList.querySelectorAll('.task-text'))
          .map(el => el.textContent.toLowerCase().trim());
        
        // Filter suggestions to avoid duplicates
        const filteredSuggestions = data.suggestions.filter(suggestion => {
          // Skip suggestions that are already in the task list by title
          const suggestionText = suggestion.text.toLowerCase().trim();
          if (existingTaskTexts.includes(suggestionText)) {
            console.log(`Skipping suggestion already in task list: ${suggestion.text}`);
            return false;
          }
          
          // Skip suggestions for emails that are already processed
          const processedEmailIds = JSON.parse(localStorage.getItem('processedEmailIds') || '[]');
          if (suggestion.email_id && (
            deletedEventIds.includes(suggestion.email_id) || 
            processedEmailIds.includes(suggestion.email_id) || 
            document.querySelector(`.task-item[data-email-id="${suggestion.email_id}"]`)
          )) {
            console.log(`Skipping suggestion from processed email: ${suggestion.email_id}`);
            return false;
          }
          
          return true;
        });
        
        if (filteredSuggestions.length > 0) {
          filteredSuggestions.forEach(addSuggestion);
        } else {
          suggestionBox.innerHTML = '<div class="no-suggestions">No new suggestions found</div>';
        }
      } else {
        suggestionBox.innerHTML = '<div class="no-suggestions">No suggestions found based on your interests</div>';
      }
    } catch (error) {
      if (error.message === 'Authentication required') {
        // This will be handled by handleApiResponse
        return;
      }
      throw error;
    }
  } catch (error) {
    console.error("Error:", error);
    suggestionBox.innerHTML = `<div class="error">Failed to load suggestions: ${error.message}</div>`;
  }
}

// Add styles for suggestion enhancements
function addStyles() {
  const style = document.createElement('style');
  style.textContent = `
    .suggested-item {
      background: white;
      padding: 15px;
      border-radius: 8px;
      margin-bottom: 10px;
      box-shadow: 0 2px 5px rgba(0,0,0,0.05);
      transition: all 0.3s ease;
    }
    
    .urgent-suggestion {
      border-left: 4px solid #ef4444;
      background-color: #fef2f2;
    }
    
    .suggested-item .deadline {
      font-size: 0.85rem;
      color: #6b7280;
      margin: 5px 0;
    }
    
    .suggested-item .location {
      font-size: 0.85rem;
      color: #4b5563;
      margin: 5px 0;
    }
    
    .suggested-item .email-link {
      display: inline-block;
      font-size: 0.85rem;
      color: #4f46e5;
      text-decoration: none;
      margin: 5px 0;
    }
    
    .suggestion-actions {
      display: flex;
      gap: 8px;
      margin-top: 10px;
    }
    
    .event-link {
      display: inline-block;
      font-size: 0.85rem;
      color: #4f46e5;
      text-decoration: none;
      margin-top: 5px;
    }
    
    .delete-btn {
      min-width: 28px;
    }
    
    .notification {
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      border-radius: 8px;
      color: white;
      font-weight: 500;
      z-index: 1000;
      display: none;
      box-shadow: 0 3px 10px rgba(0,0,0,0.2);
      animation: slideIn 0.3s ease;
    }
    
    .notification.info {
      background-color: #3b82f6;
    }
    
    .notification.success {
      background-color: #10b981;
    }
    
    .notification.error {
      background-color: #ef4444;
    }
    
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }

    .loading {
      text-align: center;
      padding: 20px;
      color: #6b7280;
    }

    .error {
      text-align: center;
      padding: 20px;
      color: #ef4444;
      background-color: #fee2e2;
      border-radius: 8px;
    }

    .no-suggestions {
      text-align: center;
      padding: 20px;
      color: #6b7280;
      background-color: #f3f4f6;
      border-radius: 8px;
    }
    
    /* Fix for scrollable containers */
    #suggestedList {
      max-height: 60vh; /* Restore to original height while keeping scrollable */
      min-height: 300px; /* Ensure minimum height */
      overflow-y: auto;
      scrollbar-width: thin;
      padding-right: 5px;
    }
    
    .suggested-section {
      height: 100%;
      max-height: 80vh; /* Restore to original height */
      display: flex;
      flex-direction: column;
    }
    
    .suggested-section h1 {
      margin-bottom: 15px;
    }
    
    /* Ensure panels are properly sized */
    .collapsible-panel {
      height: 100%;
      max-height: 80vh; /* Restore to original height */
      overflow: hidden;
    }
    
    /* Scrollbar styling */
    #suggestedList::-webkit-scrollbar,
    #chat-messages::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    
    #suggestedList::-webkit-scrollbar-track,
    #chat-messages::-webkit-scrollbar-track {
      background: rgba(0,0,0,0.05);
      border-radius: 3px;
    }
    
    #suggestedList::-webkit-scrollbar-thumb,
    #chat-messages::-webkit-scrollbar-thumb {
      background: rgba(0,0,0,0.15);
      border-radius: 3px;
    }
    
    #suggestedList::-webkit-scrollbar-thumb:hover,
    #chat-messages::-webkit-scrollbar-thumb:hover {
      background: rgba(0,0,0,0.25);
    }

    /* Add styles for time period filter dropdown */
    .filter-container {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
      padding: 0 10px;
    }
    .filter-container label {
      margin-right: 8px;
      font-weight: bold;
    }
    .filter-dropdown {
      padding: 5px 10px;
      border-radius: 4px;
      border: 1px solid #ccc;
      background-color: #fff;
      font-size: 14px;
    }
  `;
  document.head.appendChild(style);
}

// Add styles for chat command functionality
function addChatStyles() {
  const style = document.createElement('style');
  style.textContent = `
    /* Command Suggestions */
    .command-suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0;
      padding: 10px;
      background-color: #f3f4f6;
      border-radius: 8px;
      animation: fadeIn 0.3s ease;
    }
    
    .command-suggestion {
      padding: 6px 12px;
      background-color: #e0e7ff;
      color: #4338ca;
      border-radius: 16px;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
    }
    
    .command-suggestion:hover {
      background-color: #818cf8;
      color: white;
    }
    
    /* Bot message formatting */
    .bot-message a {
      color: #4f46e5;
      text-decoration: none;
      border-bottom: 1px dotted;
    }
    
    .bot-message a:hover {
      color: #4338ca;
      border-bottom: 1px solid;
    }
    
    .bot-message code {
      background-color: #f3f4f6;
      padding: 2px 4px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 0.9em;
    }
    
    .bot-message strong {
      font-weight: 600;
    }
    
    /* Fix chat layout */
    .chat-section {
      display: flex;
      flex-direction: column;
      height: 100%;
      max-height: 80vh; /* Restore height to original size */
      overflow: hidden;
    }
    
    .chat-section h1 {
      margin-bottom: 15px;
      flex-shrink: 0;
    }
    
    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 10px;
      margin-bottom: 10px;
      min-height: 300px; /* Ensure minimum height */
      max-height: 60vh; /* Limit maximum height */
      scrollbar-width: thin;
    }
    
    .chat-message {
      max-width: 85%;
      margin-bottom: 10px;
      padding: 10px 15px;
      border-radius: 10px;
      word-wrap: break-word;
    }
    
    .user-message {
      background-color: #e0e7ff;
      color: #4338ca;
      margin-left: auto;
    }
    
    .bot-message {
      background-color: #f3f4f6;
      color: #1f2937;
    }
    
    .input-container {
      display: flex;
      padding: 10px;
      background-color: white;
      border-radius: 8px;
      box-shadow: 0 -2px 5px rgba(0,0,0,0.05);
      margin-top: auto;
      gap: 8px;
      flex-shrink: 0;
    }
  `;
  document.head.appendChild(style);
}

// Event Listeners
document.addEventListener('DOMContentLoaded', async () => {
  // First check session before loading anything
  const isSessionValid = await checkSession();
  if (!isSessionValid) {
    return; // Stop initialization if session is invalid
  }
  
  setupPanel('left-trigger', 'left-panel');
  setupPanel('right-trigger', 'right-panel');
  
  // Add enhanced styles
  addStyles();
  addChatStyles(); // Add chat-specific styles
  
  // Make sure scrollable areas are properly initialized
  fixScrollableAreas();
  
  // Load calendar events
  loadCalendarEvents();
  
  // Suggestions
  document.getElementById('refresh-sug').addEventListener('click', getSuggestions);
  getSuggestions(); // Load suggestions on page load
  
  // Suggested items actions
  suggestionBox.addEventListener('click', async (e) => {
      if (e.target.classList.contains('add-btn')) {
          const suggestionItem = e.target.closest('.suggested-item');
          const text = suggestionItem.querySelector('.text').textContent;
          const deadlineEl = suggestionItem.querySelector('.deadline');
          const deadline = deadlineEl ? deadlineEl.textContent.replace('📅 ', '') : '';
          
          // Get all possible date information from the suggestion item
          const eventDate = suggestionItem.dataset.eventDate || '';
          const deadlineData = suggestionItem.dataset.deadline || deadline;
          
          console.log("Adding suggestion to tasks with date info:", {
            text,
            eventDate,
            deadline: deadlineData
          });
          
          // Check if this task already exists
          if (isDuplicateTask(text)) {
            showNotification('This task already exists in your list!', 'error');
            suggestionItem.remove();
            return;
          }
          
          try {
              // Add to calendar via API with all possible date information
              const response = await fetch("/addtask", {
                method: "POST",
                headers: { 
                  "Content-Type": "application/json",
                  'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                  task_text: text,
                  event_date: eventDate,        // Original date string from AI extraction
                  raw_deadline: deadlineData,   // Raw deadline string
                  display_date: deadline,       // Formatted display date
                  debug_info: {                 // Extra debug info
                    has_event_date: !!eventDate,
                    has_deadline: !!deadline,
                    dom_attributes: Object.keys(suggestionItem.dataset)
                  }
                }),
                credentials: "include"
              });

              try {
                const data = await handleApiResponse(response);
                
                // Extract event ID from URL if available
                let eventId = null;
                if (data.event) {
                  eventId = extractEventIdFromUrl(data.event);
                  if (eventId) {
                    console.log(`Added suggested task with calendar event ID: ${eventId}`);
                    
                    // Add to current event IDs
                    const currentEventIds = JSON.parse(localStorage.getItem('currentEventIds') || '[]');
                    if (!currentEventIds.includes(eventId)) {
                      currentEventIds.push(eventId);
                      localStorage.setItem('currentEventIds', JSON.stringify(currentEventIds));
                    }
                  }
                }
                
                // Store the email ID as processed if it exists
                if (suggestionItem.querySelector('.email-link')) {
                  const emailLink = suggestionItem.querySelector('.email-link').getAttribute('href');
                  const emailIdMatch = emailLink.match(/\/inbox\/([^/]+)/);
                  if (emailIdMatch && emailIdMatch[1]) {
                    const emailId = emailIdMatch[1];
                    const processedEmails = JSON.parse(localStorage.getItem('processedEmails') || '[]');
                    if (!processedEmails.includes(emailId)) {
                      processedEmails.push(emailId);
                      localStorage.setItem('processedEmails', JSON.stringify(processedEmails));
                    }
                  }
                }
                
                // Add to UI
                addTask(data.response || text, data.deadline || deadline, data.event, eventId);
                
                // Show success notification
                showNotification('Task added to calendar!', 'success');
                
                // Remove the suggestion after adding
                suggestionItem.remove();
              } catch (error) {
                if (error.message === 'Authentication required') {
                  // This will be handled by handleApiResponse
                  return;
                }
                throw error;
              }
          } catch (error) {
              console.error("Error adding suggested task:", error);
              showNotification(`Error adding task: ${error.message}`, 'error');
              // Fallback to local-only task
              addTask(text, deadline);
              suggestionItem.remove();
          }
      }
      if (e.target.classList.contains('delete-btn')) {
          const suggestionItem = e.target.closest('.suggested-item');
          
          // Store the email ID as processed if it exists
          if (suggestionItem.querySelector('.email-link')) {
            const emailLink = suggestionItem.querySelector('.email-link').getAttribute('href');
            const emailIdMatch = emailLink.match(/\/inbox\/([^/]+)/);
            if (emailIdMatch && emailIdMatch[1]) {
              const emailId = emailIdMatch[1];
              const processedEmails = JSON.parse(localStorage.getItem('processedEmails') || '[]');
              if (!processedEmails.includes(emailId)) {
                processedEmails.push(emailId);
                localStorage.setItem('processedEmails', JSON.stringify(processedEmails));
              }
            }
          }
          
          suggestionItem.remove();
      }
  });
  
  // Chat
  sendButton.addEventListener('click', sendMessage);
  userInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendMessage();
  });
  
  // Add @ completion for commands
  userInput.addEventListener('input', (e) => {
    if (e.target.value === '@') {
      showCommandSuggestions();
    }
  });
  
  // Welcome message for new users
  if (!localStorage.getItem('chatWelcomeSeen')) {
    setTimeout(() => {
      addMessage("👋 Hi there! I'm your RunDown assistant. Ask me anything about your tasks or try commands like @add, @remove, or @list. Type @help to see all commands.", false, true);
      localStorage.setItem('chatWelcomeSeen', 'true');
      
      // Make sure the message is visible by scrolling to the bottom
      const chatMessages = document.getElementById('chat-messages');
      if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    }, 1000);
  }
  
  // Add window resize handler to fix scroll areas
  window.addEventListener('resize', fixScrollableAreas);
});

// Helper function to fix scrollable areas
function fixScrollableAreas() {
  const suggestedList = document.getElementById('suggestedList');
  const chatMessages = document.getElementById('chat-messages');
  
  // Fix for suggested list
  if (suggestedList) {
    // Use fixed heights rather than dynamic calculations
    suggestedList.style.maxHeight = '60vh';
    suggestedList.style.minHeight = '300px';
    suggestedList.style.overflowY = 'auto';
  }
  
  // Fix for chat messages
  if (chatMessages) {
    // Use fixed heights rather than dynamic calculations
    chatMessages.style.maxHeight = '60vh';
    chatMessages.style.minHeight = '300px';
    chatMessages.style.overflowY = 'auto';
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

// Helpers
function showInputError(message) {
  taskInput.placeholder = message;
  taskInput.classList.add('error');
  setTimeout(() => {
      taskInput.classList.remove('error');
      taskInput.placeholder = 'Add a new task...';
  }, 2000);
}

// Event Delegation for Tasks
taskList.addEventListener('click', async (e) => {
  if (e.target.classList.contains('delete-btn')) {
    const taskItem = e.target.closest('.task-item');
    const eventId = taskItem.dataset.eventId;
    
    // If there's an event ID, delete from calendar
    if (eventId) {
      try {
        const deleteButton = e.target;
        // Change the button to indicate deletion in progress
        deleteButton.textContent = 'Deleting...';
        deleteButton.disabled = true;
        
        console.log(`Deleting calendar event with ID: ${eventId}`);
        const response = await fetch('/calendar/delete', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ event_id: eventId }),
          credentials: 'include'
        });
        
        // Handle the response with our utility function
        try {
          const responseData = await handleApiResponse(response);
          console.log('Response from deletion API:', responseData);
          
          // Success - show feedback before removing
          deleteButton.textContent = 'Success';
          showNotification('Event deleted successfully from calendar!', 'success');
          
          // Store deleted event IDs to prevent re-suggesting
          const deletedEventIds = JSON.parse(localStorage.getItem('deletedEventIds') || '[]');
          if (!deletedEventIds.includes(eventId)) {
            deletedEventIds.push(eventId);
            localStorage.setItem('deletedEventIds', JSON.stringify(deletedEventIds));
          }
          
          // Also store the email ID to prevent re-suggesting
          const emailId = taskItem.dataset.emailId;
          if (emailId) {
            const processedEmailIds = JSON.parse(localStorage.getItem('processedEmailIds') || '[]');
            if (!processedEmailIds.includes(emailId)) {
              processedEmailIds.push(emailId);
              localStorage.setItem('processedEmailIds', JSON.stringify(processedEmailIds));
            }
          }
          
          setTimeout(() => {
            taskItem.remove();
          }, 500);
        } catch (error) {
          if (error.message === 'Authentication required') {
            // This will be handled by handleApiResponse
            return;
          }
          
          console.error('Failed to delete calendar event:', error.message);
          showNotification(`Failed to delete calendar event: ${error.message}`, 'error');
          // Show error but still remove from UI
          deleteButton.textContent = 'Failed';
          setTimeout(() => {
            taskItem.remove();
          }, 1000);
        }
      } catch (error) {
        console.error('Error deleting calendar event:', error);
        showNotification(`Error deleting event: ${error.message}`, 'error');
        taskItem.remove(); // Still remove from UI even if API fails
      }
    } else {
      // No calendar event associated, just remove from UI
      taskItem.remove();
    }
  }
});

taskList.addEventListener('change', (e) => {
  if (e.target.classList.contains('status-select')) {
    const status = e.target.value;
    const indicator = e.target.closest('.task-item').querySelector('.status-indicator');
    indicator.className = `status-indicator status-${status}`;
  }
});