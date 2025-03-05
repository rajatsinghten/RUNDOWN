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

// Task Management
const taskInput = document.getElementById('taskInput');
const taskDeadline = document.getElementById('taskDeadline');
const addTaskBtn = document.getElementById('addTaskBtn');
const taskList = document.getElementById('taskList');
const suggestionBox = document.getElementById('suggestedList');

const createTaskElement = (taskText, deadline) => {
  const li = document.createElement('li');
  li.className = 'task-item';
  li.innerHTML = `
      <div class="task-content">
          <div class="status-indicator status-not-started"></div>
          <div>
              <span class="task-text">${taskText}</span>
              ${deadline ? `<div class="task-deadline">📅 ${new Date(deadline).toLocaleString()}</div>` : ''}
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
taskList.addEventListener('click', (e) => {
  if (e.target.classList.contains('delete-btn')) {
      e.target.closest('.task-item').remove();
  }
});

taskList.addEventListener('change', (e) => {
  if (e.target.classList.contains('status-select')) {
      const status = e.target.value;
      const indicator = e.target.closest('.task-item').querySelector('.status-indicator');
      indicator.className = `status-indicator status-${status.replace(' ', '-')}`;
  }
});

function addTask(taskValue, deadline = '') {
  if (taskValue === "") return;
  
  const taskElement = createTaskElement(taskValue, deadline);
  taskList.appendChild(taskElement);
}

addTaskBtn.addEventListener('click', () => {
  const taskText = taskInput.value.trim();
  const deadline = taskDeadline.value;
  
  if (!taskText) {
      showInputError('Please enter a task!');
      return;
  }

  addTask(taskText, deadline);
  taskInput.value = '';
  taskDeadline.value = '';
  taskInput.focus();
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
      if (message.toLowerCase().includes('add')) {
          const response = await fetch("/addtask", {
              method: "POST",
              headers: { "Content-Type": "text/plain" },
              body: message,
              credentials: "include"
          });

          if (!response.ok) throw new Error("Network response was not ok");
          
          const data = await response.json();
          addTask(data.response);
          addMessage("Task added successfully!", false);
      } else {
          const response = await fetch("/chat", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message }),
              credentials: "include"
          });

          if (!response.ok) throw new Error("Network response was not ok");
          
          const data = await response.json();
          addMessage(data.response, false);
      }
  } catch (error) {
      console.error("Error:", error);
      addMessage("Sorry, there was an error processing your request.", false);
  }
}

// Suggestions Functionality
function addSuggestion(text) {
  if (text === "") return;
  const div = document.createElement('div');
  div.innerHTML = `
      <div class="suggested-item">
          <p class="text">${text}</p>
          <button class="btn add-btn">Add</button>
          <button class="btn delete-btn">Delete</button>
      </div>`;
  suggestionBox.appendChild(div);
}

async function getSuggestions() {
  try {
      const response = await fetch("/addsuggestion", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include"
      });

      if (!response.ok) throw new Error("Network response was not ok");

      const data = await response.json();
      if (data.responses?.length) {
          data.responses.forEach(addSuggestion);
      }
  } catch (error) {
      console.error("Error:", error);
      alert("Couldn't load suggestions!");
  }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  setupPanel('left-trigger', 'left-panel');
  setupPanel('right-trigger', 'right-panel');
  
  // Suggestions
  document.getElementById('refresh-sug').addEventListener('click', getSuggestions);
  
  // Suggested items actions
  suggestionBox.addEventListener('click', (e) => {
      if (e.target.classList.contains('add-btn')) {
          const text = e.target.closest('.suggested-item').querySelector('.text').textContent;
          addTask(text);
      }
      if (e.target.classList.contains('delete-btn')) {
          e.target.closest('.suggested-item').remove();
      }
  });
});

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendMessage();
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