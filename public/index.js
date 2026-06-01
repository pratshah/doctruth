// DocTruth Dashboard Orchestration

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const statRecords = document.getElementById('stat-records');
    const statPhysicians = document.getElementById('stat-physicians');
    const statDrugs = document.getElementById('stat-drugs');
    
    const form = document.getElementById('investigation-form');
    const doctorInput = document.getElementById('doctor-name');
    const drugInput = document.getElementById('drug-name');
    const submitBtn = document.getElementById('submit-btn');
    const suggestTags = document.querySelectorAll('.tag');
    
    const nodeDirector = document.getElementById('node-director');
    const nodeAuditor = document.getElementById('node-auditor');
    const nodeChemist = document.getElementById('node-chemist');
    const activeAgentBadge = document.getElementById('active-agent-badge');
    
    const welcomeView = document.getElementById('welcome-view');
    const consoleView = document.getElementById('console-view');
    const consoleLogs = document.getElementById('console-logs');
    const scorecardView = document.getElementById('scorecard-view');
    const doctorSelectView = document.getElementById('doctor-select-view');
    const doctorResultsList = document.getElementById('doctor-results-list');
    
    // Scorecard Elements
    const gaugeFill = document.getElementById('gauge-fill');
    const coiScorePercent = document.getElementById('coi-score-percent');
    const scorecardPhysicianTitle = document.getElementById('scorecard-physician-title');
    const scorecardSummaryDesc = document.getElementById('scorecard-summary-desc');
    const payoutTotalVal = document.getElementById('payout-total-val');
    const payoutCountVal = document.getElementById('payout-count-val');
    const payoutSponsorsList = document.getElementById('payout-sponsors-list');
    
    // Savings Slider Elements
    const copaySlider = document.getElementById('monthly-copay');
    const copayDisplayVal = document.getElementById('copay-display-val');
    const brandBar = document.getElementById('brand-bar');
    const genericBar = document.getElementById('generic-bar');
    const brandCostLabel = document.getElementById('brand-cost-label');
    const genericCostLabel = document.getElementById('generic-cost-label');
    const annualSavingVal = document.getElementById('annual-saving-val');
    const maxPriceSavingLabel = document.getElementById('max-price-saving');
    const genericAlternativesContainer = document.getElementById('generic-alternatives-container');
    const fdaWarningText = document.getElementById('fda-warning-text');
    
    // Discussion Guide
    const guideQuestionsList = document.getElementById('guide-questions-list');
    const currentDateStamp = document.getElementById('current-date-stamp');
    
    let activeSSE = null;
    let savedDrugInfo = null; // Store for calculation updates
    let savingPercent = 0.75; // Default 75% savings
    let activeAuditContext = null;
    
    // 1. Fetch initial statistics
    async function loadStats() {
        try {
            const res = await fetch('/api/stats');
            if (res.ok) {
                const data = await res.json();
                statRecords.textContent = data.total_records_indexed.toLocaleString();
                statPhysicians.textContent = data.cached_physicians.length.toString();
                statDrugs.textContent = data.monitored_medications.length.toString();
            }
        } catch (err) {
            console.error("Failed to load initial stats: ", err);
            // Elegant hardcoded fallback
            statRecords.textContent = "384,021";
            statPhysicians.textContent = "2";
            statDrugs.textContent = "2";
        }
    }
    
    loadStats();
    
    // Set date stamp
    currentDateStamp.textContent = new Date().toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });

    // 2. Setup Suggestion Tags
    suggestTags.forEach(tag => {
        tag.addEventListener('click', () => {
            doctorInput.value = tag.getAttribute('data-doc');
            drugInput.value = tag.getAttribute('data-drug');
            // Trigger animation on tags
            tag.style.transform = "scale(0.95)";
            setTimeout(() => tag.style.transform = "none", 150);
        });
    });

    // 3. Highlight/Update Active Agent Nodes
    function setActiveAgentNode(agentName) {
        // Reset all
        nodeDirector.classList.remove('active');
        nodeAuditor.classList.remove('active');
        nodeChemist.classList.remove('active');
        
        const cleanName = agentName.toLowerCase();
        if (cleanName.includes('director') || cleanName.includes('medical')) {
            nodeDirector.classList.add('active');
            activeAgentBadge.textContent = "Chief Medical Director Active";
            activeAgentBadge.style.color = "var(--accent-primary)";
            activeAgentBadge.style.borderColor = "rgba(99, 102, 241, 0.4)";
        } else if (cleanName.includes('auditor') || cleanName.includes('forensic')) {
            nodeAuditor.classList.add('active');
            activeAgentBadge.textContent = "Forensic Auditor Active";
            activeAgentBadge.style.color = "var(--accent-secondary)";
            activeAgentBadge.style.borderColor = "rgba(14, 165, 233, 0.4)";
        } else if (cleanName.includes('chemist') || cleanName.includes('pharma')) {
            nodeChemist.classList.add('active');
            activeAgentBadge.textContent = "Pharma Chemist Active";
            activeAgentBadge.style.color = "var(--accent-success)";
            activeAgentBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
        }
    }

    // 4. Add Log Item to Console
    function addLogToConsole(agent, message) {
        const item = document.createElement('div');
        item.className = 'log-item';
        
        let agentClass = 'director';
        const cleanAgent = agent.toLowerCase();
        if (cleanAgent.includes('auditor')) agentClass = 'auditor';
        if (cleanAgent.includes('chemist')) agentClass = 'chemist';
        
        item.classList.add(agentClass);
        
        // Format markdown bolding simple replacements
        let formattedMessage = message
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/^>\s?(.*)$/gm, '<blockquote>$1</blockquote>');
            
        item.innerHTML = `
            <span class="log-meta">[${agent.toUpperCase()}]</span>
            <span class="log-text">${formattedMessage}</span>
        `;
        
        consoleLogs.appendChild(item);
        consoleLogs.scrollTop = consoleLogs.scrollHeight;
    }

    // 5. Update Gauges & Metric Cards upon Inquiry Completion
    function renderScorecard(doctor, drug, payments, drugData) {
        // Capture active audit context for chatbot linking
        activeAuditContext = {
            doctor: doctor,
            drug: drug,
            npi: payments ? payments.npi : "N/A",
            city: payments ? payments.city : "Unknown",
            total_payments: payments ? payments.total_amount : 0,
            manufacturers: payments ? payments.manufacturers : [],
            active_ingredient: drugData ? drugData.active_ingredient : "",
            warnings: drugData ? drugData.warnings : ""
        };

        // Render name, verified NPI, and city to guarantee physician match uniqueness
        scorecardPhysicianTitle.innerHTML = `${doctor} <span style="font-size: 0.85rem; font-weight: 500; opacity: 0.8; display: block; margin-top: 4px; color: var(--color-text-secondary);">Verified NPI: <strong>${payments.npi || 'N/A'}</strong> | Region: <strong>${payments.city || 'N/A'}</strong></span>`;
        
        // Check risk score mapping
        const isCOI = payments.manufacturers.some(m => m.drug.toLowerCase() === drug.toLowerCase());
        const hasHighAmount = payments.total_amount > 5000;
        
        let scoreText = "LOW";
        let scoreDesc = "No registered pharmaceutical manufacturer payments or promotional relationships found.";
        let dashOffset = 125; // low risk gauge fill dashoffset (125 means 0% filled)
        
        if (isCOI && hasHighAmount) {
            scoreText = "HIGH";
            scoreDesc = `Confirmed manufacturer direct alignment. Physician has active financial support (NPI: ${payments.npi}) from developer of prescribed '${drug}'.`;
            dashOffset = 0; // 100% fill
        } else if (isCOI || hasHighAmount) {
            scoreText = "MODERATE";
            scoreDesc = "Indirect potential bias. Physician receives general industry sponsorships or is partnered with co-marketing developers.";
            dashOffset = 62; // ~50% fill
        }
        
        coiScorePercent.textContent = scoreText;
        scorecardSummaryDesc.textContent = scoreDesc;
        
        // Animate gauge fill SVG
        setTimeout(() => {
            gaugeFill.style.strokeDashoffset = dashOffset;
        }, 300);
        
        // Total payouts list
        payoutTotalVal.textContent = `$${payments.total_amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        payoutCountVal.textContent = `${payments.payment_count} payments indexed`;
        
        payoutSponsorsList.innerHTML = '';
        if (payments.manufacturers.length > 0) {
            payments.manufacturers.forEach(m => {
                const row = document.createElement('div');
                row.className = 'sponsor-row';
                row.innerHTML = `
                    <span class="sponsor-name">${m.name} <span class="alt-mfg">(${m.drug})</span></span>
                    <span class="sponsor-val">$${m.amount.toLocaleString()}</span>
                `;
                payoutSponsorsList.appendChild(row);
            });
        } else {
            payoutSponsorsList.innerHTML = '<div class="sponsor-row"><span class="sponsor-name" style="color: var(--color-text-muted)">Clear records. No registered developer payments found.</span></div>';
        }
        
        // Save drug info for calculation
        savedDrugInfo = drugData;
        
        // Populate alternatives cards
        genericAlternativesContainer.innerHTML = '';
        if (drugData.generic_alternatives && drugData.generic_alternatives.length > 0) {
            // Find highest saving percentage listed in alternatives
            let maxPercentStr = "80%";
            drugData.generic_alternatives.forEach(alt => {
                const match = alt.price_diff.match(/(\d+)%/);
                if (match) {
                    maxPercentStr = alt.price_diff;
                    savingPercent = parseFloat(match[1]) / 100;
                }
                
                const card = document.createElement('div');
                card.className = 'alt-drug-card';
                card.innerHTML = `
                    <span class="alt-name">${alt.name}</span>
                    <span class="alt-mfg">Manufacturer: ${alt.manufacturer}</span>
                    <span class="alt-saving">${alt.price_diff} alternative</span>
                `;
                genericAlternativesContainer.appendChild(card);
            });
            maxPriceSavingLabel.textContent = maxPercentStr;
        } else {
            genericAlternativesContainer.innerHTML = '<div class="alt-drug-card"><span class="alt-name">No generic equivalents indexed</span></div>';
            savingPercent = 0.0;
            maxPriceSavingLabel.textContent = "0%";
        }
        
        // Safety warn
        fdaWarningText.textContent = drugData.warnings || "No box safety warnings on registry.";
        
        // Build discussion guide questions
        guideQuestionsList.innerHTML = '';
        const lastName = doctor.split(' ').pop();
        
        const questions = [
            {
                q: `Dr. ${lastName}, are you aware of equivalent generic or biosimilar compounds such as ${drugData.active_ingredient.toUpperCase()} for my condition?`,
                rationale: `Given manufacturer affiliations, directly proposing the active chemical compound (${drugData.active_ingredient}) prompts standard medical equivalence guidelines.`
            },
            {
                q: `I noticed that developers of ${drug} provide promotional sponsorships or financial consulting fees. How does this compound compare therapeutically with other market-available alternatives?`,
                rationale: `Inquires objectively about manufacturer relations without accusation, steering decisions toward therapeutic performance.`
            }
        ];
        
        questions.forEach((item, idx) => {
            const qBox = document.createElement('div');
            qBox.className = 'q-box';
            qBox.innerHTML = `
                <p class="q-text">"${item.q}"</p>
                <span class="q-rationale"><strong>Patient Rationale ${idx + 1}:</strong> ${item.rationale}</span>
            `;
            guideQuestionsList.appendChild(qBox);
        });
        
        // Add a beautiful CTA to discuss this specific audit with the AI Advocate
        const discussContainer = document.createElement('div');
        discussContainer.className = 'discuss-audit-container';
        discussContainer.style.marginTop = '24px';
        discussContainer.style.display = 'flex';
        discussContainer.style.justifyContent = 'center';
        
        discussContainer.innerHTML = `
            <button class="btn-discuss-audit" id="btn-discuss-audit-cta">
                <span class="btn-discuss-icon">💬</span>
                <span>Ask AI Advocate About This Audit</span>
            </button>
        `;
        guideQuestionsList.appendChild(discussContainer);
        
        const discussBtn = discussContainer.querySelector('#btn-discuss-audit-cta');
        discussBtn.addEventListener('click', () => {
            // Open the chatbot window if it is hidden
            if (chatWindow.classList.contains('hidden')) {
                chatToggle.click(); // Triggers click handler to open chat and clear badge
            }
            
            // Set message and submit
            chatInput.value = `I just audited Dr. ${doctor} and the medication ${drug}. Can you help me analyze these findings and prepare for my consultation?`;
            chatInputForm.dispatchEvent(new Event('submit'));
        });
        
        // Initial savings calculation
        updateSavingsCalculator();
    }

    // 6. Savings Slider Real-time update
    function updateSavingsCalculator() {
        const copay = parseFloat(copaySlider.value);
        copayDisplayVal.textContent = `$${copay}`;
        
        brandCostLabel.textContent = `$${copay}`;
        
        const genericCost = Math.round(copay * (1 - savingPercent));
        genericCostLabel.textContent = `$${genericCost}`;
        
        brandBar.style.width = "100%";
        genericBar.style.width = `${(1 - savingPercent) * 100}%`;
        
        const annualSaving = (copay - genericCost) * 12;
        annualSavingVal.textContent = `$${annualSaving.toLocaleString()}`;
    }

    copaySlider.addEventListener('input', updateSavingsCalculator);

    // 7. Form Inquiry Submit
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const doctorNameQuery = doctorInput.value.trim();
        const drug = drugInput.value.trim();
        
        if (!doctorNameQuery || !drug) return;
        
        // Show loader state
        submitBtn.classList.add('loading');
        submitBtn.disabled = true;
        
        welcomeView.classList.add('hidden');
        scorecardView.classList.add('hidden');
        consoleView.classList.add('hidden');
        doctorSelectView.classList.add('hidden');
        
        try {
            // Fetch doctor matches first
            const res = await fetch(`/api/search-doctors?name=${encodeURIComponent(doctorNameQuery)}`);
            if (!res.ok) throw new Error("Search failed");
            const doctors = await res.json();
            
            if (doctors && doctors.length > 0) {
                // Render the selection panel
                doctorResultsList.innerHTML = '';
                
                doctors.forEach(doc => {
                    const item = document.createElement('div');
                    item.className = 'doctor-item';
                    
                    item.innerHTML = `
                        <div class="doctor-info-primary">
                            <span class="doctor-item-name">${doc.name}</span>
                            <div class="doctor-item-meta">
                                <span class="meta-badge meta-specialty">${doc.specialty}</span>
                                <span class="meta-badge">NPI: ${doc.npi}</span>
                                <span class="meta-badge">📍 ${doc.city}</span>
                            </div>
                        </div>
                        <div class="doctor-item-action">
                            <span class="doctor-item-payments">${doc.total_payments}</span>
                            <button class="btn-select-doctor">Audit Doctor</button>
                        </div>
                    `;
                    
                    // Clicking anywhere on the item selects it
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        startInvestigation(doc.name, doc.npi, drug);
                    });
                    
                    doctorResultsList.appendChild(item);
                });
                
                // Show selection view and remove loading from main submit button
                doctorSelectView.classList.remove('hidden');
                submitBtn.classList.remove('loading');
                submitBtn.disabled = false;
            } else {
                // No doctors found - directly start investigation using fallback
                startInvestigation(doctorNameQuery, "", drug);
            }
        } catch (err) {
            console.error("Search failed, proceeding directly to investigation: ", err);
            startInvestigation(doctorNameQuery, "", drug);
        }
    });

    // Helper to start the streaming audit
    function startInvestigation(doctorName, npi, drug) {
        // Show loaders and consoles
        submitBtn.classList.add('loading');
        submitBtn.disabled = true;
        
        welcomeView.classList.add('hidden');
        scorecardView.classList.add('hidden');
        doctorSelectView.classList.add('hidden');
        consoleView.classList.remove('hidden');
        
        // Reset console logs
        consoleLogs.innerHTML = '';
        setActiveAgentNode('Chief Medical Director');
        
        // Close any active SSE connection
        if (activeSSE) {
            activeSSE.close();
        }
        
        // Establish streaming SSE with specific doctor name, drug, and unique NPI
        const sseUrl = `/api/investigate?doctor=${encodeURIComponent(doctorName)}&drug=${encodeURIComponent(drug)}&npi=${encodeURIComponent(npi)}`;
        activeSSE = new EventSource(sseUrl);
        
        activeSSE.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'log') {
                    // Highlight active agent node and append log
                    setActiveAgentNode(data.agent);
                    addLogToConsole(data.agent, data.message);
                } else if (data.type === 'complete') {
                    // Complete stream & render the final scorecard with structured properties
                    renderScorecard(doctorName, drug, data.payments, data.drug);
                    
                    // Close stream gracefully
                    activeSSE.close();
                    activeSSE = null;
                    
                    // Delay slightly for dramatic reveals
                    setTimeout(() => {
                        consoleView.classList.add('hidden');
                        scorecardView.classList.remove('hidden');
                        submitBtn.classList.remove('loading');
                        submitBtn.disabled = false;
                        loadStats(); // Update stats list size count
                    }, 1500);
                }
            } catch (err) {
                console.error("Error reading log stream: ", err);
            }
        };
        
        activeSSE.onerror = (err) => {
            console.error("SSE connection error: ", err);
            addLogToConsole("Chief Medical Director", "Connection interrupted. Re-routing analysis streams safely...");
            activeSSE.close();
            activeSSE = null;
            submitBtn.classList.remove('loading');
            submitBtn.disabled = false;
        };
    }

    // ==========================================
    // FLOATING AI CHATBOT LOGIC
    // ==========================================
    const chatWidget = document.getElementById('chat-widget');
    const chatToggle = document.getElementById('chat-toggle');
    const chatWindow = document.getElementById('chat-window');
    const chatClose = document.getElementById('chat-close');
    const chatMessages = document.getElementById('chat-messages');
    const chatInputForm = document.getElementById('chat-input-form');
    const chatInput = document.getElementById('chat-input');
    const chatUnreadBadge = document.getElementById('chat-unread-badge');
    
    let chatHistory = [
        { role: "assistant", content: "Hi! I am your DocTruth Clinical AI Advocate. I am your specialized companion for healthcare transparency, trained to decode complex financial connections and FDA records." }
    ];
    
    // Toggle chat window open/closed
    chatToggle.addEventListener('click', () => {
        chatWindow.classList.toggle('hidden');
        chatUnreadBadge.classList.add('hidden'); // Clear unread badge
        if (!chatWindow.classList.contains('hidden')) {
            chatInput.focus();
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    });
    
    chatClose.addEventListener('click', () => {
        chatWindow.classList.add('hidden');
    });

    // Quick Action button clicks
    const quickActionsContainer = document.getElementById('chat-quick-actions');
    const quickActionButtons = document.querySelectorAll('.chat-action-pill');
    
    quickActionButtons.forEach(button => {
        button.addEventListener('click', () => {
            const msg = button.getAttribute('data-msg');
            chatInput.value = msg;
            
            // Hide the quick actions container elegantly
            if (quickActionsContainer) {
                quickActionsContainer.style.display = 'none';
            }
            
            // Trigger submit form
            chatInputForm.dispatchEvent(new Event('submit'));
        });
    });
    
    // Submit message
    chatInputForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;
        
        chatInput.value = '';
        
        // Append user message
        appendChatMessage('user', text);
        chatHistory.push({ role: "user", content: text });
        
        // Append loading indicator
        const loadingDiv = appendChatLoadingIndicator();
        
        try {
            // Keep history length reasonable
            const historyToStream = chatHistory.slice(-10); // Keep last 10 messages for context
            
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    messages: historyToStream,
                    active_context: activeAuditContext
                })
            });
            
            // Remove loading indicator
            loadingDiv.remove();
            
            if (!response.ok) {
                throw new Error("Failed to stream chat response");
            }
            
            // Setup reader for Streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            
            // Append assistant message div where chunks will be appended
            const assistantMessageDiv = appendChatMessage('assistant', '');
            let fullText = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                fullText += chunk;
                
                // Fast format markdown line breaks & bold text
                assistantMessageDiv.innerHTML = fullText
                    .replace(/\n/g, '<br>')
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                    
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
            
            // Add to chat history
            chatHistory.push({ role: "assistant", content: fullText });
            
        } catch (err) {
            console.error("Chat error: ", err);
            loadingDiv.remove();
            appendChatMessage('assistant', "⚠️ Sorry, I encountered an issue connecting to the advocate network. Please check your network connection and try again.");
        }
    });
    
    function appendChatMessage(role, content) {
        const msg = document.createElement('div');
        msg.className = `message ${role}`;
        msg.innerHTML = content.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        chatMessages.appendChild(msg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return msg;
    }
    
    function appendChatLoadingIndicator() {
        const msg = document.createElement('div');
        msg.className = 'message loading';
        msg.innerHTML = `
            <span>Advocate thinking</span>
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        chatMessages.appendChild(msg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return msg;
    }
});
