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

const createTaskElement = (taskText, deadline, eventUrl = null, eventId = null) => {
  const li = document.createElement('li');
  li.className = 'task-item';
  
  // Store event ID as data attribute if provided
  if (eventId) {
    li.dataset.eventId = eventId;
  }
  
  li.innerHTML = `
      <div class="task-content">
          <div class="status-indicator status-not-started"></div>
          <div>
              <span class="task-text">${taskText}</span>
              ${deadline ? `<div class="task-deadline">📅 ${deadline}</div>` : ''}
              ${eventUrl ? `<a href="${eventUrl}" target="_blank" class="event-link">🔗 Calendar Event</a>` : ''}
          </div>
      </div>
      <div class="task-controls">
          <select class="status-select">
              <option value="not-started">Not Started</option>
              <option value="in-progress">In Progress</option>
              <option value="completed">Completed</option>
          </select>
          <button class="delete-btn">🗑️</button>
      </div>
  `;
  return li;
};

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
          deleteButton.textContent = '⏳';
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
            deleteButton.textContent = '✅';
            showNotification('Event deleted successfully from calendar!', 'success');
            
            // Store deleted event IDs to prevent re-suggesting
            const deletedEventIds = JSON.parse(localStorage.getItem('deletedEventIds') || '[]');
            if (!deletedEventIds.includes(eventId)) {
              deletedEventIds.push(eventId);
              localStorage.setItem('deletedEventIds', JSON.stringify(deletedEventIds));
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
            deleteButton.textContent = '❌';
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
      indicator.className = `status-indicator status-${status.replace(' ', '-')}`;
  }
});

function addTask(taskValue, deadline, eventUrl = null, eventId = null) {
  if (taskValue === "") return;
  
  const taskElement = createTaskElement(taskValue, deadline, eventUrl, eventId);
  taskList.appendChild(taskElement);
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
      addTask(data.response || taskText, displayDeadline, data.event, eventId);
      
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

// Chat Functionality
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');

function addMessage(message, isUser = true) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${isUser ? 'user-message' : 'bot-message'}`;

  const lines = message.split('\n');
  lines.forEach((line, index) => {
      messageDiv.appendChild(document.createTextNode(line));
      if (index !== lines.length - 1) {
          messageDiv.appendChild(document.createElement('br'));
      }
  });

  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
  const message = userInput.value.trim();
  if (!message) return;

  addMessage(message, true);
  userInput.value = '';

  try {
      const response = await fetch("/chat", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ message }),
          credentials: "include"
      });

      try {
        const data = await handleApiResponse(response);
        addMessage(data.response, false);
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

// Helper function to check if an item already exists in the to-do list
function isDuplicateTask(taskText) {
  const existingTasks = Array.from(taskList.querySelectorAll('.task-text'))
    .map(el => el.textContent.toLowerCase().trim());
  return existingTasks.includes(taskText.toLowerCase().trim());
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
          
          addTask(title, start, event.htmlLink, event.id);
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
  suggestionBox.innerHTML = '<div class="loading">Loading suggestions...</div>';
  try {
      const response = await fetch("/addsuggestion", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            'X-Requested-With': 'XMLHttpRequest'
          },
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
              if (suggestion.email_id && deletedEventIds.includes(suggestion.email_id)) {
                console.log(`Skipping suggestion from deleted email: ${suggestion.email_id}`);
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
});

// Helpers
function showInputError(message) {
  taskInput.placeholder = message;
  taskInput.classList.add('error');
  setTimeout(() => {
      taskInput.classList.remove('error');
      taskInput.placeholder = 'Add a new task...';
  }, 2000);
}