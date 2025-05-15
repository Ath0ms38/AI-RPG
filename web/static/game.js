document.addEventListener('DOMContentLoaded', async function() {
    // DOM Elements
    const characterCreationModal = document.getElementById('character-creation-modal');
    const worldDescription = document.getElementById('world-description');
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
    const loadingOverlay = document.getElementById('loading-overlay');

    // Status bar setup
    // (Removed global status bar injection. Status bars will be rendered in characterStats.)

    // Templates
    const userMessageTemplate = document.getElementById('user-message-template');
    const aiMessageTemplate = document.getElementById('ai-message-template');
    const systemMessageTemplate = document.getElementById('system-message-template');
    const toolCallTemplate = document.getElementById('tool-call-template');

    // State
    let sessionId = null;
    let webSocket = null;
    let currentAiMessage = null;
    let characterCreated = false;
    let pendingToolCalls = {};  // To track pending tool calls

    // Get story_id from body attribute if present
    const storyId = document.body.getAttribute('data-story-id');
    if (storyId) {
        // If a story_id is present, use it as the session id (continue story)
        sessionId = storyId;
        characterCreationModal.classList.add('hidden');
        fetchStoryDataAndInit();

    } else {
        characterCreationModal.classList.remove('hidden');
    }

    async function fetchStoryDataAndInit() {
        await fetchCharacterData();
        await fetchAndRenderChatHistory();
        connectWebSocket();
    }

    async function fetchAndRenderChatHistory() {
        try {
            const response = await fetch(`/story/${sessionId}`);
            const data = await response.json ? await response.json() : await response;
            if (data && data.chat_history && Array.isArray(data.chat_history)) {
                // Collect all legacy observation messages in a batch
                let pendingObservations = [];
                // For tool call/output pairing
                let pendingToolCall = null;

                data.chat_history.forEach(msg => {
                    // Hide system guidelines and "Begin the adventure"
                    if (
                        (msg.role === 'system' && msg.content && msg.content.includes('RPG Game Master Guidelines')) ||
                        (msg.role === 'human' && msg.content && (
                            msg.content.trim() === 'Begin the adventure.' ||
                            msg.content.trim().startsWith('World Description:')
                        ))
                    ) {
                        return;
                    }
                    // Handle legacy observation messages
                    if (
                        msg.role &&
                        msg.role.toLowerCase().startsWith('ai') &&
                        msg.content &&
                        msg.content.startsWith('Observation AI called Tool')
                    ) {
                        // Parse observation tool call and collect
                        const observation = parseObservationMessage(msg.content);
                        if (Array.isArray(observation)) {
                            pendingObservations.push(...observation);
                        } else {
                            pendingObservations.push(observation);
                        }
                        return;
                    }

                    // If we reach a non-observation message and have pending observations, render them
                    if (pendingObservations.length > 0) {
                        addObservationMessage(pendingObservations);
                        pendingObservations = [];
                    }

                    // Skip empty AI messages
                    if (
                        msg.role &&
                        msg.role.toLowerCase().startsWith('ai') &&
                        (!msg.content || !msg.content.trim())
                    ) {
                        return;
                    }

                    // Tool call/output pairing (assumes tool_call and tool_output are in chat_history)
                    if (msg.type === 'tool_call') {
                        pendingToolCall = {
                            name: msg.name,
                            args: JSON.stringify(msg.args, null, 2),
                            output: null
                        };
                        return;
                    }
                    if (msg.type === 'tool_output' && pendingToolCall) {
                        pendingToolCall.output = msg.content;
                        addCombinedToolMessage(
                            pendingToolCall.name,
                            pendingToolCall.args,
                            pendingToolCall.output
                        );
                        pendingToolCall = null;
                        return;
                    }
                    // Only render descriptive tool call messages as expanders
                    if (
                        msg.role &&
                        msg.role.toLowerCase().startsWith('ai') &&
                        msg.content &&
                        msg.content.startsWith('Tool AI called Tool')
                    ) {
                        // Extract tool name from descriptive format
                        let toolName = "Tool";
                        let args = "";
                        let output = msg.content || "";
                        // Match: Tool AI called Tool TOOL_NAME with arguments: ... and got response:\nRESULT
                        const regex = /^Tool AI called Tool ([^ ]+)(?: with arguments: (.*?))? and got response:\n([\s\S]*)$/;
                        const match = msg.content.match(regex);
                        if (match) {
                            toolName = match[1].trim();
                            args = match[2] ? match[2].trim() : "";
                            output = match[3] ? match[3].trim() : "";
                        }
                        addCombinedToolMessage(
                            toolName,
                            args,
                            output
                        );
                        return;
                    }

                    // Render regular messages
                    if (msg.role === 'human') {
                        addUserMessage(msg.content);
                    } else if (msg.role === 'system') {
                        addSystemMessage(msg.content);
                    } else if (msg.role && msg.role.toLowerCase().startsWith('ai')) {
                        appendToAiMessage(msg.content);
                        finalizeAiMessage();
                    }
                });
                // Render any remaining observations at the end
                if (pendingObservations.length > 0) {
                    addObservationMessage(pendingObservations);
                }
            }
        } catch (error) {
            console.error('Error fetching chat history:', error);
        }
    }

    // Helper to parse observation messages from legacy AI chat history
    function parseObservationMessage(content) {
        // Example: "Observation AI called Tool see_inventory and got response:\n Your inventory is empty."
        // or: "Observation AI called Tool see_equipment and got response:\n {...}"
        // Try to extract tool and output
        const regex = /^Observation AI called Tool ([^ ]+) and got response:\n([\s\S]*)$/;
        const match = content.match(regex);
        if (match) {
            return [{
                tool: match[1],
                output: match[2].trim()
            }];
        }
        // fallback: return as a single observation
        return [{
            tool: "Observation",
            output: content
        }];
    }

    // Event Listeners
    createCharacterButton.addEventListener('click', createCharacter);
    characterDescription.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            createCharacter();
        }
    });
    worldDescription.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
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
    async function initializeSession(worldDesc, charDesc) {
        try {
            showLoading();
            // Create a new story and wait for backend to finish character/AI
            const response = await fetch('/api/stories', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    world_description: worldDesc,
                    character_description: charDesc
                })
            });

            const data = await response.json();
            hideLoading();

            if (data.success) {
                window.location.href = `/game/${data.story_id}`;
            } else {
                creationStatus.textContent = data.message || "Error creating story.";
            }
        } catch (error) {
            hideLoading();
            console.error('Error initializing session:', error);
            creationStatus.textContent = 'Error initializing game. Please refresh the page.';
        }
    }

    function showLoading() {
        if (loadingOverlay) loadingOverlay.style.display = 'flex';
    }
    function hideLoading() {
        if (loadingOverlay) loadingOverlay.style.display = 'none';
    }

    function connectWebSocket(onOpenCallback) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;

        webSocket = new WebSocket(wsUrl);

        webSocket.onopen = () => {
            console.log('WebSocket connected');
            if (onOpenCallback) onOpenCallback();
        };

        webSocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        };

        webSocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            addSystemMessage('Connection error. Please refresh the page.');
        };

        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;

        webSocket.onclose = (event) => {
            console.log('WebSocket closed', event);
            // Only reconnect if not a clean close and retry limit not reached
            if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                setTimeout(() => {
                    if (sessionId) {
                        connectWebSocket();
                    }
                }, 3000 * reconnectAttempts); // Exponential backoff
            } else if (reconnectAttempts >= maxReconnectAttempts) {
                addSystemMessage('Unable to connect to server. Please refresh the page or try again later.');
            }
        };
    }

    function createCharacter() {
        const worldDesc = worldDescription.value.trim();
        const charDesc = characterDescription.value.trim();
        if (!worldDesc || !charDesc) {
            creationStatus.textContent = "Please enter both world and character descriptions.";
            return;
        }
        creationStatus.textContent = "Creating your adventure... Please wait.";
        initializeSession(worldDesc, charDesc);
    }

    function handleWebSocketMessage(message) {
        switch (message.type) {
            case 'system':
                addSystemMessage(message.content);
                break;
            case 'user':
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
                pendingToolCalls[message.name] = {
                    name: message.name,
                    args: JSON.stringify(message.args, null, 2),
                    output: null
                };
                break;
            case 'tool_output':
                const matchingToolName = Object.keys(pendingToolCalls).find(
                    toolName => !pendingToolCalls[toolName].output
                );
                if (matchingToolName) {
                    pendingToolCalls[matchingToolName].output = message.content;
                    addCombinedToolMessage(
                        matchingToolName,
                        pendingToolCalls[matchingToolName].args,
                        message.content
                    );
                    delete pendingToolCalls[matchingToolName];
                } else {
                    addToolOutputMessage(message.content);
                }
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

    function addCombinedToolMessage(toolName, args, output) {
        const toolMessage = document.createElement('div');
        toolMessage.className = 'tool-message';
        const toolHeader = document.createElement('div');
        toolHeader.className = 'tool-header';
        toolHeader.innerHTML = `
            <i class="fa fa-wrench"></i>
            <span class="tool-name">${toolName}</span>
            <i class="fa fa-chevron-down tool-toggle-icon"></i>
        `;
        const toolContent = document.createElement('div');
        toolContent.className = 'tool-content';
        toolContent.innerHTML = `
            <div class="tool-args">
                <strong>Arguments:</strong>
                <pre>${args}</pre>
            </div>
            <div class="tool-result">
                <strong>Result:</strong>
                <pre>${output}</pre>
            </div>
        `;
        toolContent.style.display = 'none';
        toolMessage.appendChild(toolHeader);
        toolMessage.appendChild(toolContent);
        chatHistory.appendChild(toolMessage);
        toolHeader.addEventListener('click', function() {
            if (toolContent.style.display === 'none') {
                toolContent.style.display = 'block';
                toolHeader.querySelector('.tool-toggle-icon').className = 'fa fa-chevron-up tool-toggle-icon';
            } else {
                toolContent.style.display = 'none';
                toolHeader.querySelector('.tool-toggle-icon').className = 'fa fa-chevron-down tool-toggle-icon';
            }
            scrollToBottom();
        });
        scrollToBottom();
    }

    function sendMessage() {
        if (!characterCreated && !storyId) {
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
        const observationContainer = document.createElement('div');
        observationContainer.className = 'message observation-container';
        const observationHeader = document.createElement('div');
        observationHeader.className = 'observation-header';
        observationHeader.innerHTML = `
            <i class="fa fa-eye"></i>
            <span>Observation AI</span>
            <i class="fa fa-chevron-down observation-toggle-icon"></i>
        `;
        const observationContent = document.createElement('div');
        observationContent.className = 'observation-content';
        if (observations && observations.length > 0) {
            observations.forEach(obs => {
                const toolDiv = document.createElement('div');
                toolDiv.className = 'tool-item';
                toolDiv.innerHTML = `<strong>${obs.tool}:</strong> ${obs.output}`;
                observationContent.appendChild(toolDiv);
            });
        } else {
            const noObsDiv = document.createElement('div');
            noObsDiv.className = 'tool-item';
            noObsDiv.textContent = 'No observations to report.';
            observationContent.appendChild(noObsDiv);
        }
        observationContent.style.display = 'none';
        observationContainer.appendChild(observationHeader);
        observationContainer.appendChild(observationContent);
        chatHistory.appendChild(observationContainer);
        observationHeader.addEventListener('click', function() {
            if (observationContent.style.display === 'none') {
                observationContent.style.display = 'block';
                observationHeader.querySelector('.observation-toggle-icon').className = 'fa fa-chevron-up observation-toggle-icon';
            } else {
                observationContent.style.display = 'none';
                observationHeader.querySelector('.observation-toggle-icon').className = 'fa fa-chevron-down observation-toggle-icon';
            }
            scrollToBottom();
        });
        scrollToBottom();
    }

    function appendToAiMessage(content) {
        if (!currentAiMessage) {
            const template = aiMessageTemplate.content.cloneNode(true);
            currentAiMessage = template.querySelector('.message-content');
            chatHistory.appendChild(template);
        }
        currentAiMessage.textContent += content;
        scrollToBottom();
    }

    function finalizeAiMessage() {
        currentAiMessage = null;
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
        if (data.name && document.activeElement !== characterName) {
            characterName.value = data.name;
        }
        if (data.lore && document.activeElement !== characterLore) {
            characterLore.value = data.lore;
        }
        if (data.health && data.level) {
            characterStats.innerHTML = `
                <div class="status-item health">
                    <span class="status-label"><i class="fa fa-heart"></i> Health:</span>
                    <span class="status-value">${data.health.current_health}/${data.health.max_health}</span>
                    <div class="status-bar-bg">
                        <div class="status-bar-fill health-bar" style="width:${100 * data.health.current_health / data.health.max_health}%;"></div>
                    </div>
                </div>
                <div class="status-item mana">
                    <span class="status-label"><i class="fa fa-bolt"></i> Mana:</span>
                    <span class="status-value">${data.health.current_mana}/${data.health.max_mana}</span>
                    <div class="status-bar-bg">
                        <div class="status-bar-fill mana-bar" style="width:${100 * data.health.current_mana / data.health.max_mana}%;"></div>
                    </div>
                </div>
                <div class="status-item xp">
                    <span class="status-label"><i class="fa fa-star"></i> XP:</span>
                    <span class="status-value">${data.level.experience}/${data.level.experience_to_next_level}</span>
                    <div class="status-bar-bg">
                        <div class="status-bar-fill xp-bar" style="width:${100 * data.level.experience / data.level.experience_to_next_level}%;"></div>
                    </div>
                </div>
                <div class="stat-item">
                    <span>Level: ${data.level.level}</span>
                </div>
            `;
        }
        if (data.equipment) {
            equipmentSlots.innerHTML = '';
            for (const [slot, item] of Object.entries(data.equipment)) {
                const slotDiv = document.createElement('div');
                slotDiv.classList.add('equipment-item');
                let display = 'Empty';
                if (item && typeof item === 'object') {
                    display = `${item.name} (x${item.amount}, ${item.rarity})`;
                } else if (typeof item === 'string') {
                    display = item;
                }
                // Map slot keys to icon filenames
                const slotIconMap = {
                    head: "head.svg",
                    chest: "chest.svg",
                    legs: "legs.svg",
                    feet: "feet.svg",
                    hands: "hands.svg",
                    main_hand: "mainhand.svg",
                    off_hand: "offhand.svg"
                };
                const iconFile = slotIconMap[slot] || "default.svg";
                slotDiv.innerHTML = `
                    <img src="/static/icons/${iconFile}" alt="${slot}" class="equipment-icon">
                    <span>${formatSlotName(slot)}</span>
                    <span>${display}</span>
                `;
                equipmentSlots.appendChild(slotDiv);
            }
        }
        if (data.inventory) {
            inventoryList.innerHTML = '';
            if (data.inventory === "Your inventory is empty.") {
                const emptyDiv = document.createElement('div');
                emptyDiv.textContent = "Your inventory is empty.";
                inventoryList.appendChild(emptyDiv);
            } else {
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
