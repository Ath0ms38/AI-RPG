document.addEventListener('DOMContentLoaded', async function() {
    // DOM Elements
    const characterCreationModal = document.getElementById('character-creation-modal');
    const characterDescription = document.getElementById('character-description');
    const createCharacterButton = document.getElementById('create-character-button');
    const creationStatus = document.getElementById('creation-status');
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const characterName = document.getElementById('character-name');
    const characterLore = document.getElementById('character-lore');
    const characterStats = document.getElementById('character-stats');
    const equipmentSlots = document.getElementById('equipment-slots');
    const inventoryList = document.getElementById('inventory-list');

    // Templates
    const userMessageTemplate = document.getElementById('user-message-template');
    const aiMessageTemplate = document.getElementById('ai-message-template');
    const systemMessageTemplate = document.getElementById('system-message-template');
    const observationMessageTemplate = document.getElementById('observation-message-template');
    const toolCallTemplate = document.getElementById('tool-call-template');

    // State
    let sessionId = null;
    let webSocket = null;
    let currentAiMessage = null;
    let characterCreated = false;

    // Initialize the game
    await initializeSession();

    // Event Listeners
    createCharacterButton.addEventListener('click', createCharacter);
    characterDescription.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            createCharacter();
        }
    });

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Character data editing
    characterName.addEventListener('blur', updateCharacterData);
    characterLore.addEventListener('blur', updateCharacterData);

    // Functions
    async function initializeSession() {
        try {
            // Create a new session
            const response = await fetch('/session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();
            sessionId = data.session_id;

            // Fetch initial character data
            fetchCharacterData();

            // Connect WebSocket
            connectWebSocket();
        } catch (error) {
            console.error('Error initializing session:', error);
            addSystemMessage('Error initializing game. Please refresh the page.');
        }
    }

    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;

        webSocket = new WebSocket(wsUrl);

        webSocket.onopen = () => {
            console.log('WebSocket connected');
        };

        webSocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        };

        webSocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            addSystemMessage('Connection error. Please refresh the page.');
        };

        webSocket.onclose = () => {
            console.log('WebSocket closed');
            // Attempt to reconnect if unexpectedly closed
            setTimeout(() => {
                if (sessionId) {
                    connectWebSocket();
                }
            }, 3000);
        };
    }

    function createCharacter() {
        const description = characterDescription.value.trim();
        if (!description) {
            creationStatus.textContent = "Please enter a character description.";
            return;
        }

        creationStatus.textContent = "Creating your character... Please wait.";

        if (webSocket && webSocket.readyState === WebSocket.OPEN) {
            webSocket.send(description);

            // Listen for character creation completion
            const originalOnMessage = webSocket.onmessage;
            webSocket.onmessage = (event) => {
                const message = JSON.parse(event.data);

                if (message.type === 'character_update') {
                    // Character has been created
                    characterCreated = true;

                    // Hide modal
                    characterCreationModal.classList.add('hidden');

                    // Add a system message about successful character creation
                    addSystemMessage("Character creation successful! Your adventure begins...");

                    // Restore original message handler
                    webSocket.onmessage = originalOnMessage;

                    // Handle the current message
                    handleWebSocketMessage(message);
                } else {
                    // Process tool calls and outputs during creation but don't show in chat
                    if (message.type === 'tool_call' || message.type === 'tool_output') {
                        // Just update the creation status
                        if (message.type === 'tool_call') {
                            creationStatus.textContent = `Creating character... Setting up ${message.name}`;
                        } else if (message.type === 'tool_output') {
                            creationStatus.textContent = "Character details finalized...";
                        }
                    } else {
                        // Handle other message types
                        handleWebSocketMessage(message);
                    }

                    // Check if character creation is complete
                    if (message.type === 'system' && message.content === 'GAME STARTED!') {
                        characterCreated = true;
                        characterCreationModal.classList.add('hidden');

                        // Add success message instead of original system message
                        addSystemMessage("Character creation successful! Your adventure begins...");

                        webSocket.onmessage = originalOnMessage;
                    }
                }
            };
        } else {
            creationStatus.textContent = "Connection lost. Please refresh the page.";
        }
    }

    function handleWebSocketMessage(message) {
        switch (message.type) {
            case 'system':
                addSystemMessage(message.content);
                break;
            case 'user':
                // Already handled when sending
                break;
            case 'ai_chunk':
                appendToAiMessage(message.content);
                break;
            case 'ai_complete':
                finalizeAiMessage();
                break;
            case 'observation':
                addObservationMessage(message.content);
                break;
            case 'tool_call':
                addToolCallMessage(message.name, JSON.stringify(message.args, null, 2));
                break;
            case 'tool_output':
                addToolOutputMessage(message.content);
                break;
            case 'character_update':
                updateCharacterUI(message.data);
                break;
            case 'error':
                addSystemMessage(`Error: ${message.content}`);
                break;
            default:
                console.log('Unknown message type:', message);
        }
    }

    function sendMessage() {
        // Don't allow sending messages until character is created
        if (!characterCreated) {
            return;
        }

        const message = userInput.value.trim();
        if (!message) return;

        addUserMessage(message);

        if (webSocket && webSocket.readyState === WebSocket.OPEN) {
            webSocket.send(message);
        } else {
            addSystemMessage('Connection lost. Please refresh the page.');
        }

        userInput.value = '';
    }

    function addUserMessage(content) {
        const template = userMessageTemplate.content.cloneNode(true);
        template.querySelector('.message-content').textContent = content;
        chatHistory.appendChild(template);
        scrollToBottom();
    }

    function addSystemMessage(content) {
        const template = systemMessageTemplate.content.cloneNode(true);
        template.querySelector('.message-content').textContent = content;
        chatHistory.appendChild(template);
        scrollToBottom();
    }

    function addObservationMessage(observations) {
        const template = observationMessageTemplate.content.cloneNode(true);
        const contentDiv = template.querySelector('.observation-content');

        observations.forEach(obs => {
            const toolDiv = document.createElement('div');
            toolDiv.classList.add('tool-item');
            toolDiv.innerHTML = `<strong>${obs.tool}:</strong> ${obs.output}`;
            contentDiv.appendChild(toolDiv);
        });

        const observationDiv = chatHistory.appendChild(template);

        // Add toggle functionality
        const toggleButton = observationDiv.querySelector('.toggle-button');
        const observationContent = observationDiv.querySelector('.observation-content');
        const toggleIcon = toggleButton.querySelector('i');

        toggleButton.addEventListener('click', function() {
            observationContent.classList.toggle('collapsed');
            toggleIcon.classList.toggle('fa-chevron-down');
            toggleIcon.classList.toggle('fa-chevron-up');
        });

        scrollToBottom();
    }

    function appendToAiMessage(content) {
        if (!currentAiMessage) {
            const template = aiMessageTemplate.content.cloneNode(true);
            currentAiMessage = template.querySelector('.message-content');
            chatHistory.appendChild(template);
        }

        currentAiMessage.innerHTML += content;
        scrollToBottom();
    }

    function finalizeAiMessage() {
        currentAiMessage = null;
    }

    function addToolCallMessage(toolName, args) {
        const template = toolCallTemplate.content.cloneNode(true);
        template.querySelector('.tool-name').textContent = toolName;
        template.querySelector('.tool-content').textContent = args;

        const toolMessage = chatHistory.appendChild(template);

        // Add toggle functionality to tool calls
        const toolHeader = toolMessage.querySelector('.tool-header');
        const toolContent = toolMessage.querySelector('.tool-content');

        // Initially collapse the tool content
        toolContent.classList.add('collapsed');

        // Add click handler for toggling
        toolHeader.addEventListener('click', function() {
            toolContent.classList.toggle('collapsed');
        });

        scrollToBottom();
    }

    function addToolOutputMessage(content) {
        const div = document.createElement('div');
        div.classList.add('tool-output-message');
        div.textContent = content;
        chatHistory.appendChild(div);
        scrollToBottom();
    }

    async function fetchCharacterData() {
        try {
            const response = await fetch(`/character/${sessionId}`);
            const data = await response.json();

            if (data.error) {
                console.error('Error fetching character data:', data.error);
                return;
            }

            updateCharacterUI(data);
        } catch (error) {
            console.error('Error fetching character data:', error);
        }
    }

    async function updateCharacterData() {
        const updateData = {
            name: characterName.value.trim(),
            lore: characterLore.value.trim()
        };

        try {
            const response = await fetch(`/character/${sessionId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });

            const data = await response.json();

            if (data.error) {
                console.error('Error updating character data:', data.error);
                return;
            }

            updateCharacterUI(data);
        } catch (error) {
            console.error('Error updating character data:', error);
        }
    }

    function updateCharacterUI(data) {
        // Update name and lore if they exist and aren't focused
        if (data.name && document.activeElement !== characterName) {
            characterName.value = data.name;
        }

        if (data.lore && document.activeElement !== characterLore) {
            characterLore.value = data.lore;
        }

        // Update stats
        if (data.health && data.level) {
            characterStats.innerHTML = '';

            // Health and Mana
            const healthManaDiv = document.createElement('div');
            healthManaDiv.innerHTML = `
                <div class="stat-item">
                    <span>Health:</span> 
                    <span>${data.health.current_health}/${data.health.max_health}</span>
                </div>
                <div class="stat-item">
                    <span>Mana:</span> 
                    <span>${data.health.current_mana}/${data.health.max_mana}</span>
                </div>
            `;
            characterStats.appendChild(healthManaDiv);

            // Level and XP
            const levelDiv = document.createElement('div');
            levelDiv.innerHTML = `
                <div class="stat-item">
                    <span>Level:</span> 
                    <span>${data.level.level}</span>
                </div>
                <div class="stat-item">
                    <span>XP:</span> 
                    <span>${data.level.experience}/${data.level.experience_to_next_level}</span>
                </div>
            `;
            characterStats.appendChild(levelDiv);
        }

        // Update equipment
        if (data.equipment) {
            equipmentSlots.innerHTML = '';

            for (const [slot, item] of Object.entries(data.equipment)) {
                const slotDiv = document.createElement('div');
                slotDiv.classList.add('equipment-item');

                slotDiv.innerHTML = `
                    <span>${formatSlotName(slot)}:</span>
                    <span>${item || 'Empty'}</span>
                `;

                equipmentSlots.appendChild(slotDiv);
            }
        }

        // Update inventory
        if (data.inventory) {
            inventoryList.innerHTML = '';

            if (data.inventory === "Your inventory is empty.") {
                const emptyDiv = document.createElement('div');
                emptyDiv.textContent = "Your inventory is empty.";
                inventoryList.appendChild(emptyDiv);
            } else {
                // Basic parsing of the inventory string
                const lines = data.inventory.split('\n');

                for (let i = 2; i < lines.length; i++) {
                    const line = lines[i];
                    if (line && !line.startsWith('===')) {
                        const itemDiv = document.createElement('div');
                        itemDiv.classList.add('inventory-item');
                        itemDiv.textContent = line;
                        inventoryList.appendChild(itemDiv);
                    }
                }
            }
        }
    }

    function formatSlotName(slot) {
        return slot.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    }

    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
});