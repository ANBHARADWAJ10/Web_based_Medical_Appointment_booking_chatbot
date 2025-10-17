// Chat widget state management
let chatIsOpen = false;
let isDarkTheme = true;
let sessionId = generateSessionId();

// Generate unique session ID
function generateSessionId() {
    return 'session_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
}

// Theme toggle functionality
function toggleTheme() {
    const chatWindow = document.querySelector('.chat-window');
    const body = document.body;
    const themeIcon = document.querySelector('.theme-toggle i');
    
    isDarkTheme = !isDarkTheme;
    
    if (isDarkTheme) {
        body.classList.remove('light-theme');
        body.classList.add('dark-theme');
        chatWindow.classList.remove('light-theme');
        chatWindow.classList.add('dark-theme');
        themeIcon.className = 'fas fa-sun';
    } else {
        body.classList.remove('dark-theme');
        body.classList.add('light-theme');
        chatWindow.classList.remove('dark-theme');
        chatWindow.classList.add('light-theme');
        themeIcon.className = 'fas fa-moon';
    }
    
    localStorage.setItem('medical-chatbot-theme', isDarkTheme ? 'dark' : 'light');
}

// Load saved theme on page load
function loadTheme() {
    const savedTheme = localStorage.getItem('medical-chatbot-theme') || 'dark';
    const chatWindow = document.querySelector('.chat-window');
    const body = document.body;
    const themeIcon = document.querySelector('.theme-toggle i');
    
    isDarkTheme = savedTheme === 'dark';
    
    if (isDarkTheme) {
        body.classList.add('dark-theme');
        chatWindow.classList.add('dark-theme');
        themeIcon.className = 'fas fa-sun';
    } else {
        body.classList.add('light-theme');
        chatWindow.classList.add('light-theme');
        themeIcon.className = 'fas fa-moon';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.focus();
    }
    chatIsOpen = true; // Always open
});

// Auto-resize textarea
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// Handle Enter key press
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
    if (event.key === 'Escape') {
        closeChatWidget();
    }
}

// Send message functionality
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const message = input.value.trim();
    
    if (message === '') return;

    // Check for "end" command
    if (message.toLowerCase() === 'end') {
        showEndConfirmation();
        input.value = '';
        return;
    }

    // Disable input and button
    input.disabled = true;
    sendButton.disabled = true;
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Clear input
    input.value = '';
    input.style.height = 'auto';
    
    // Show typing indicator
    showTypingIndicator();
    
    try {
        // Send message to backend
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        removeTypingIndicator();
        
        if (response.ok) {
            // Add bot response with buttons if needed
            addBotMessage(data);
            
            // Handle special response types
            if (data.type === 'booking_confirmed') {
                showBookingConfirmation(data.unique_code);
            }
        } else {
            addMessage(data.error || 'Sorry, something went wrong. Please try again.', 'assistant', true);
        }
        
    } catch (error) {
        console.error('Error sending message:', error);
        removeTypingIndicator();
        addMessage('Sorry, I\'m having trouble connecting. Please try again.', 'assistant', true);
    } finally {
        // Re-enable input and button
        input.disabled = false;
        sendButton.disabled = false;
        input.focus();
    }
}

// Show end confirmation dialog
function showEndConfirmation() {
    const messagesContainer = document.getElementById('messagesContainer');
    
    // Add confirmation message
    const confirmationDiv = document.createElement('div');
    confirmationDiv.className = 'message assistant';
    confirmationDiv.innerHTML = `
        <div class="message-avatar">M</div>
        <div class="message-content">
            <div class="message-bubble">
                Are you sure you want to go back to the main menu? This will end your current session.
            </div>
            <div class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
        </div>
    `;
    
    messagesContainer.appendChild(confirmationDiv);
    
    // Add confirmation buttons
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'button-container';
    buttonContainer.id = 'confirmationButtons';
    
    const okButton = document.createElement('button');
    okButton.className = 'chat-option-btn menu-button';
    okButton.textContent = '✅ Yes, Go to Main Menu';
    okButton.onclick = () => confirmEndSession(true);
    
    const cancelButton = document.createElement('button');
    cancelButton.className = 'chat-option-btn';
    cancelButton.style.background = 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)';
    cancelButton.textContent = '❌ Cancel, Continue Here';
    cancelButton.onclick = () => confirmEndSession(false);
    
    buttonContainer.appendChild(okButton);
    buttonContainer.appendChild(cancelButton);
    messagesContainer.appendChild(buttonContainer);
    
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Handle end session confirmation
async function confirmEndSession(confirmed) {
    // Remove confirmation buttons
    const confirmationButtons = document.getElementById('confirmationButtons');
    if (confirmationButtons) {
        confirmationButtons.remove();
    }
    
    if (confirmed) {
        // Add user choice as message
        addMessage('Yes, Go to Main Menu', 'user');
        
        // Show typing indicator
        showTypingIndicator();
        
        try {
            // Send reset command to backend
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: 'reset_to_menu',
                    session_id: sessionId
                })
            });
            
            const data = await response.json();
            removeTypingIndicator();
            
            if (response.ok) {
                addBotMessage(data);
            }
        } catch (error) {
            console.error('Error resetting session:', error);
            removeTypingIndicator();
            addMessage('Session reset to main menu.', 'assistant');
            // Force show main menu buttons
            setTimeout(() => {
                addOptionButtons({
                    type: 'menu',
                    message: 'Back to main menu'
                });
            }, 500);
        }
    } else {
        // Add user choice as message  
        addMessage('Cancel, Continue Here', 'user');
        addMessage('Continuing with current session. How can I help you?', 'assistant');
    }
}

// Handle button click from options
function handleButtonClick(buttonText, buttonType) {
    // Add user selection as a message
    addMessage(buttonText, 'user');
    
    // Remove all option buttons after selection
    removeOptionButtons();
    
    // Send the selection to backend
    sendButtonSelection(buttonText);
}

// Send button selection to backend
async function sendButtonSelection(selection) {
    showTypingIndicator();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: selection,
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        removeTypingIndicator();
        
        if (response.ok) {
            addBotMessage(data);
            
            if (data.type === 'booking_confirmed') {
                showBookingConfirmation(data.unique_code);
            }
        } else {
            addMessage(data.error || 'Sorry, something went wrong. Please try again.', 'assistant', true);
        }
        
    } catch (error) {
        console.error('Error sending selection:', error);
        removeTypingIndicator();
        addMessage('Sorry, I\'m having trouble connecting. Please try again.', 'assistant', true);
    }
}

// Add bot message with potential buttons
function addBotMessage(data) {
    const messagesContainer = document.getElementById('messagesContainer');
    const currentTime = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    
    // Format message text (preserve line breaks)
    const formattedText = data.message.replace(/\n/g, '<br>');
    
    messageDiv.innerHTML = `
        <div class="message-avatar">M</div>
        <div class="message-content">
            <div class="message-bubble">${formattedText}</div>
            <div class="message-time">${currentTime}</div>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    
    // Add buttons if response has options
    if (data.type && shouldShowButtons(data.type)) {
        addOptionButtons(data);
    }
    
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    handleValidationPrompt(data.message);
}

// Check if response type should show buttons
function shouldShowButtons(responseType) {
    const buttonTypes = [
        'blood_group_selection',
        'gender_selection', 
        'doctor_selection',
        'date_selection',
        'time_selection',
        'menu'
    ];
    return buttonTypes.includes(responseType);
}

// Add option buttons based on response type - FIXED VERSION
function addOptionButtons(data) {
    const messagesContainer = document.getElementById('messagesContainer');
    
    let buttons = [];
    let buttonClass = 'option-button';
    let containerClass = 'button-container';
    
    switch(data.type) {
        case 'menu':
            buttons = [
                { text: '🔍 Check Booking', value: 'Check booking' },
                { text: '📅 Book Appointment', value: 'Book appointment' }
            ];
            buttonClass = 'menu-button';
            break;
            
        case 'blood_group_selection':
            if (data.options) {
                buttons = data.options.map(option => ({
                    text: option,
                    value: option
                }));
                containerClass += ' blood-group-grid';
                buttonClass = 'blood-group-btn';
            }
            break;
            
        case 'gender_selection':
            buttons = [
                { text: '👨 Male', value: 'Male' },
                { text: '👩 Female', value: 'Female' },
                { text: '⚧ Other', value: 'Other' }
            ];
            containerClass += ' gender-horizontal';
            buttonClass = 'gender-btn';
            break;
            
        case 'doctor_selection':
            if (data.doctors) {
                buttons = data.doctors.map((doctor, index) => ({
                    text: `${index + 1}. ${doctor.name}`,
                    value: `${index + 1}`,
                    subtitle: `${doctor.specialty} - ${doctor.availability || 'Available'}`
                }));
                buttonClass = 'doctor-btn';
            }
            break;
            
        case 'date_selection':
            if (data.dates) {
                buttons = data.dates.map((date, index) => ({
                    text: `${index + 1}. ${date.display_name}`,
                    value: `${index + 1}`,
                    subtitle: `${date.total_available_slots} slots available`
                }));
                buttonClass = 'date-btn';
            }
            break;
            
        case 'time_selection':
            if (data.time_slots) {
                buttons = data.time_slots.map((slot, index) => ({
                    text: `${index + 1}. ${slot.time}`,
                    value: `${index + 1}`
                }));
                buttonClass = 'time-btn';
            }
            break;
    }
    
    if (buttons.length > 0) {
        const buttonContainer = document.createElement('div');
        buttonContainer.className = containerClass;
        buttonContainer.id = 'currentButtons';
        
        // FIX: Create buttons properly in a loop
        buttons.forEach(buttonData => {
            const button = document.createElement('button');
            button.className = `${buttonClass} chat-option-btn`;
            button.onclick = () => handleButtonClick(buttonData.value, data.type);
            
            if (buttonData.subtitle) {
                button.innerHTML = `
                    <span class="button-main-text">${buttonData.text}</span>
                    <span class="button-subtitle">${buttonData.subtitle}</span>
                `;
            } else {
                button.textContent = buttonData.text;
            }
            
            // IMPORTANT: Actually add the button to the container!
            buttonContainer.appendChild(button);
        });
        
        messagesContainer.appendChild(buttonContainer);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

// Remove existing option buttons
function removeOptionButtons() {
    const existingButtons = document.getElementById('currentButtons');
    if (existingButtons) {
        existingButtons.remove();
    }
}

// Add regular message to chat
function addMessage(text, sender, isError = false) {
    const messagesContainer = document.getElementById('messagesContainer');
    const currentTime = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}${isError ? ' error' : ''}`;
    
    // Format message text (preserve line breaks)
    const formattedText = text.replace(/\n/g, '<br>');
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${sender === 'user' ? 'U' : 'M'}</div>
        <div class="message-content">
            <div class="message-bubble">${formattedText}</div>
            <div class="message-time">${currentTime}</div>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
    const messagesContainer = document.getElementById('messagesContainer');
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant typing-indicator';
    typingDiv.id = 'typingIndicator';
    
    typingDiv.innerHTML = `
        <div class="message-avatar">M</div>
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Remove typing indicator
function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Show booking confirmation with special styling
function showBookingConfirmation(uniqueCode) {
    const lastMessage = document.querySelector('.message:last-child .message-bubble');
    if (lastMessage) {
        lastMessage.style.background = 'linear-gradient(135deg, #4CAF50, #45a049)';
        lastMessage.style.color = 'white';
        lastMessage.style.boxShadow = '0 4px 12px rgba(76, 175, 80, 0.3)';
    }
}

// Handle escape key globally
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && chatIsOpen) {
        closeChatWidget();
    }
});

// Initialize chat widget on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Medical ChatBot initialized successfully!');
    
    // Load saved theme
    loadTheme();
    
    // Set initial time
    const initialTime = document.getElementById('initialTime');
    if (initialTime) {
        initialTime.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
    
    // Add initial menu buttons after a short delay
    setTimeout(() => {
        addOptionButtons({
            type: 'menu',
            message: 'Welcome! Please select an option:'
        });
    }, 1000);
    
    // Mobile scroll management
    if (window.innerWidth <= 480) {
        const originalOpenChat = openChatWidget;
        const originalCloseChat = closeChatWidget;

        window.openChatWidget = function() {
            originalOpenChat();
            document.body.style.overflow = 'hidden';
        };

        window.closeChatWidget = function() {
            originalCloseChat();
            document.body.style.overflow = '';
        };
    }
});

// Close chat widget with smooth animation
// function closeChatWidget() {
//     const chatContainer = document.querySelector('.chat-container');
//     const chatWindow = document.querySelector('.chat-window');
    
//     if (!chatContainer || !chatWindow) return;
    
//     // Add fade-out animation
//     chatWindow.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
//     chatWindow.style.opacity = '0';
//     chatWindow.style.transform = 'scale(0.95)';
    
//     // After animation completes, hide the container
//     setTimeout(() => {
//         chatContainer.style.display = 'none';
//         chatIsOpen = false;
        
//         // Restore body scroll if on mobile
//         if (window.innerWidth <= 480) {
//             document.body.style.overflow = '';
//         }
        
//         // Optional: Redirect to another page or show floating button
//         // window.location.href = '/';
//     }, 300);
// }

// function closeChatWidget() {
//     const chatContainer = document.querySelector('.chat-container');
//     const chatWindow = document.querySelector('.chat-window');
    
//     if (!chatContainer || !chatWindow) return;
    
//     // Add fade-out animation
//     chatWindow.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
//     chatWindow.style.opacity = '0';
//     chatWindow.style.transform = 'scale(0.95)';
    
//     // After animation completes, hide both elements
//     setTimeout(() => {
//         chatWindow.style.display = 'none';      // 👈 Hide chat window
//         chatContainer.style.display = 'none';   // 👈 Hide chat container completely
//         chatIsOpen = false;
        
//         // Restore body scroll if on mobile
//         if (window.innerWidth <= 480) {
//             document.body.style.overflow = '';
//         }

//         console.log('Chat window closed and hidden.');
//     }, 300);
// }


// Optional: Reopen chat widget function
function openChatWidget() {
    const chatContainer = document.querySelector('.chat-container');
    const chatWindow = document.querySelector('.chat-window');
    
    if (!chatContainer || !chatWindow) return;
    
    // Show container
    chatContainer.style.display = 'flex';
    
    // Reset and animate in
    chatWindow.style.opacity = '0';
    chatWindow.style.transform = 'scale(0.95)';
    
    setTimeout(() => {
        chatWindow.style.opacity = '1';
        chatWindow.style.transform = 'scale(1)';
        chatIsOpen = true;
        
        // Prevent body scroll on mobile
        if (window.innerWidth <= 480) {
            document.body.style.overflow = 'hidden';
        }
        
        // Focus input
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.focus();
        }
    }, 50);
}

// Add escape key handler for closing
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && chatIsOpen) {
        closeChatWidget();
    }
});

// Initialize transitions on page load
document.addEventListener('DOMContentLoaded', function() {
    const chatWindow = document.querySelector('.chat-window');
    if (chatWindow) {
        chatWindow.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    }
});


// Validations

// Validation flags
let isContactPromptActive = false;
let isNamePromptActive = false;

// Detect and enable proper validation based on bot message
function handleValidationPrompt(botMessage) {
    const lowerMsg = botMessage.toLowerCase();

    if (lowerMsg.includes('please enter your contact number')) {
        isContactPromptActive = true;
        isNamePromptActive = false;
        enableContactOnlyValidation();
        disableNameOnlyValidation();
    } else if (
        lowerMsg.includes("please enter your full name") ||
        lowerMsg.includes("enter your name") ||
        lowerMsg.includes("patient name")
    ) {
        isNamePromptActive = true;
        isContactPromptActive = false;
        enableNameOnlyValidation();
        disableContactOnlyValidation();
    } else {
        // No validation needed
        isContactPromptActive = false;
        isNamePromptActive = false;
        disableContactOnlyValidation();
        disableNameOnlyValidation();
    }
}

// === CONTACT VALIDATION ===
function enableContactOnlyValidation() {
    const input = document.getElementById('messageInput');
    if (!input) return;

    input.value = input.value.replace(/\D/g, '').slice(0, 10);
    input.setAttribute('maxlength', '10');

    disableNameOnlyValidation(); // avoid overlap
    input.removeEventListener('input', contactValidationHandler);
    input.addEventListener('input', contactValidationHandler);
}

function contactValidationHandler(e) {
    this.value = this.value.replace(/\D/g, '').slice(0, 10);
}

function disableContactOnlyValidation() {
    const input = document.getElementById('messageInput');
    if (!input) return;

    input.removeAttribute('maxlength');
    input.removeEventListener('input', contactValidationHandler);
}

// === NAME VALIDATION ===
function enableNameOnlyValidation() {
    const input = document.getElementById('messageInput');
    if (!input) return;

    input.value = input.value.replace(/[^a-zA-Z ]/g, '');
    input.setAttribute('maxlength', '50');

    disableContactOnlyValidation(); // avoid overlap
    input.removeEventListener('input', nameValidationHandler);
    input.addEventListener('input', nameValidationHandler);
}

function nameValidationHandler(e) {
    this.value = this.value.replace(/[^a-zA-Z ]/g, '');
}

function disableNameOnlyValidation() {
    const input = document.getElementById('messageInput');
    if (!input) return;

    input.removeAttribute('maxlength');
    input.removeEventListener('input', nameValidationHandler);
}



