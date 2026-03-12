// Loaded from config.js


let supabaseClient;

async function init() {
    supabaseClient = window.supabase.createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY);
    await loadAuctions();

    document.getElementById('startBtn').addEventListener('click', startBackfill);
}

async function loadAuctions() {
    const select = document.getElementById('auctionSelect');
    try {
        const { data, error } = await supabaseClient
            .from('auctions')
            .select('id, auction_name, scrape_date')
            .order('scrape_date', { ascending: false });

        if (error) throw error;

        select.innerHTML = '<option value="">Select an auction...</option>';

        data.forEach(auction => {
            const date = new Date(auction.scrape_date).toLocaleDateString();
            const option = document.createElement('option');
            option.value = auction.id;
            // Fallback for name if null + ID for clarity
            option.textContent = `${auction.auction_name || 'Unnamed'} (${date}) [ID: ${auction.id}]`;
            select.appendChild(option);
        });
    } catch (e) {
        select.innerHTML = '<option>Error loading auctions</option>';
        console.error(e);
    }
}

async function startBackfill() {
    const auctionId = document.getElementById('auctionSelect').value;
    const url = document.getElementById('urlInput').value.trim();
    const btn = document.getElementById('startBtn');
    const statusBox = document.getElementById('statusBox');

    if (!auctionId || !url) {
        alert('Please select an auction and enter a URL');
        return;
    }

    if (!CONFIG.LAMBDA_URL) {
        statusBox.classList.add('active');
        statusBox.textContent = '❌ Error: Lambda URL is not configured in config.js';
        alert('Error: Lambda URL is missing. Please check configuration.');
        return;
    }

    // UI Updates
    btn.disabled = true;
    btn.textContent = 'Processing...';
    statusBox.classList.add('active');
    statusBox.textContent = '🚀 Sending request to Lambda...';

    try {
        const response = await fetch(CONFIG.LAMBDA_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                auction_id: parseInt(auctionId)
            })
        });

        const text = await response.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch (e) {
            throw new Error(`Invalid JSON response (${response.status} ${response.statusText}): ${text.substring(0, 200)}...`);
        }

        if (response.ok) {
            statusBox.textContent = '✅ Success!\n\n' + JSON.stringify(data, null, 2);
        } else {
            statusBox.textContent = '❌ Error:\n\n' + JSON.stringify(data, null, 2);
        }

    } catch (e) {
        statusBox.textContent = '❌ Network/Client Error:\n' + e.message;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Start Backfill';
    }
}

document.addEventListener('DOMContentLoaded', init);
