document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration: Replace these with your actual Airtable details! ---
    const AIRTABLE_BASE_ID = 'app0uHGC09j4kfxn5'; // Correct based on your docs
    const AIRTABLE_TABLE_NAME = 'Tickets';       // Correct based on your docs
    const AIRTABLE_PERSONAL_ACCESS_TOKEN = 'patgpyn3GmmgKensL.e93ada40d428c9e99b17766b5edb344da2cb0f4eb6cbfc75a7d0316256b545a1'; // PASTE YOUR SECRET TOKEN
    // --------------------------------------------------------------------

    const searchBox = document.getElementById('search-box');
    const ticketListContainer = document.getElementById('ticket-list');
    const ticketDetailContainer = document.getElementById('ticket-detail');
    let allTickets = [];

    // Main function to fetch data from Airtable and render the UI
    async function initializeTracker() {
        const url = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_NAME}`;
        
        try {
            const response = await fetch(url, {
                headers: { 'Authorization': `Bearer ${AIRTABLE_PERSONAL_ACCESS_TOKEN}` }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(`Airtable API error! Status: ${response.status}. Message: ${errorData.error.message}`);
            }

            const airtableData = await response.json();
            allTickets = airtableData.records.map(record => ({
                id: record.id,
                jira_key: record.fields['Jira Key'],
                summary: record.fields['Jira Summary'],
                status: record.fields['Status'],
                created_date: record.fields['Created Date'],
                updated_date: record.fields['Updated Date'],
                resolved_date: record.fields['Resolved Date'],
                compliance_status: record.fields['Compliance Status'],
                finance_status: record.fields['Finance Status'],
                comment_ids: record.fields['Comments'] || []
            }));
            
            renderTicketList(allTickets);
        } catch (error) {
            console.error("Could not fetch ticket data from Airtable:", error);
            ticketListContainer.innerHTML = `<div class="error">Could not load ticket data. Check console for details.</div>`;
        }
    }

    // Renders the list of ticket timelines
    function renderTicketList(tickets) {
        ticketListContainer.innerHTML = '';
        if (tickets.length === 0) {
            ticketListContainer.innerHTML = '<div class="placeholder">No tickets found in Airtable.</div>';
            return;
        }
        tickets.forEach(ticket => {
            const ticketElement = document.createElement('div');
            const statusClass = (ticket.status || '').toLowerCase().replace(' ', '');
            ticketElement.className = `ticket-item status-${statusClass}`;
            
            const isComplianceApproved = ticket.compliance_status === 'Approved';
            const isFinanceApproved = ticket.finance_status === 'Validated';
            let middleDotClass = '';
            if (isComplianceApproved && isFinanceApproved) { middleDotClass = 'full-approved'; }
            else if (isComplianceApproved || isFinanceApproved) { middleDotClass = 'half-approved'; }
            
            const endDateText = ticket.resolved_date ? formatDate(ticket.resolved_date) : 'Pending';
            
            ticketElement.innerHTML = `
                <div class="ticket-title">${ticket.summary || 'No Summary'} | ${ticket.jira_key}</div>
                <div class="timeline">
                    <div class="timeline-bar"></div><div class="timeline-dot dot-start"></div>
                    <div class="timeline-dot dot-middle ${middleDotClass}"></div><div class="timeline-dot dot-end"></div>
                    <div class="timeline-label label-start">Start Date<br>${formatDate(ticket.created_date)}</div>
                    <div class="timeline-label label-middle">Approvals</div>
                    <div class="timeline-label label-end">End Date<br>${endDateText}</div>
                </div>`;

            ticketElement.addEventListener('click', () => {
                document.querySelectorAll('.ticket-item').forEach(el => el.classList.remove('active'));
                ticketElement.classList.add('active');
                renderTicketDetail(ticket);
            });
            ticketListContainer.appendChild(ticketElement);
        });
    }
    
    // Renders the detail pane on the right (Modified to fetch comments on demand)
    async function renderTicketDetail(ticket) {
        ticketDetailContainer.innerHTML = `<div class="placeholder">Loading comments...</div>`;

        let comments = [];
        if (ticket.comment_ids && ticket.comment_ids.length > 0) {
            // This formula finds comments where the "Tickets" linked field contains our ticket's ID.
            const formula = `OR(${ticket.comment_ids.map(id => `RECORD_ID()='${id}'`).join(',')})`;
            const url = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/Comments?filterByFormula=${encodeURIComponent(formula)}`;
            
            try {
                const response = await fetch(url, { headers: { 'Authorization': `Bearer ${AIRTABLE_PERSONAL_ACCESS_TOKEN}` } });
                const commentData = await response.json();
                comments = commentData.records.map(r => ({ 
                    commenter: r.fields.Commenter, 
                    date: r.fields.Date, 
                    comment: r.fields.Comment 
                })).sort((a,b) => new Date(a.date) - new Date(b.date));
            } catch (error) {
                console.error("Could not fetch comments:", error);
            }
        }
        
        const complianceStatusClass = (ticket.compliance_status || '').toLowerCase().replace(/[^a-z0-9]/g, '');
        const financeStatusClass = (ticket.finance_status || '').toLowerCase().replace(/[^a-z0-9]/g, '');
        const commentsHtml = comments.length > 0 ? comments.map(comment => `
            <div class="comment-item">
                <div class="comment-header">
                    <span class="comment-author">${comment.commenter}</span>
                    <span class="comment-date">${formatDate(comment.date, true)}</span>
                </div>
                <div class="comment-body">${(comment.comment || '').replace(/\n/g, '<br>')}</div>
            </div>`).join('') : 'No comments found for this ticket.';
        
        ticketDetailContainer.innerHTML = `
            <div id="detail-header">
                <h2>${ticket.jira_key}</h2>
                <div id="detail-pills">
                    <span class="pill status-${(ticket.status || '').toLowerCase().replace(' ', '')}">Status: ${ticket.status || 'N/A'}</span>
                    <span class="pill status-${complianceStatusClass}">Compliance: ${ticket.compliance_status || 'N/A'}</span>
                    <span class="pill status-${financeStatusClass}">Finance: ${ticket.finance_status || 'N/A'}</span>
                </div>
            </div>
            <div id="comments-container"><h3>Comments</h3>${commentsHtml}</div>`;
    }

    // Handle search input
    searchBox.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filteredTickets = allTickets.filter(ticket => 
            (ticket.jira_key || '').toLowerCase().includes(searchTerm) || 
            (ticket.summary || '').toLowerCase().includes(searchTerm)
        );
        renderTicketList(filteredTickets);
    });

    // Helper to format dates
    function formatDate(dateString, withTime = false) {
        if (!dateString) return '';
        const options = { year: 'numeric', month: 'short', day: 'numeric' };
        if (withTime) {
            options.hour = '2-digit';
            options.minute = '2-digit';
            options.hour12 = false;
        }
        return new Date(dateString).toLocaleDateString('en-US', options);
    }

    // Start the application
    initializeTracker();
});