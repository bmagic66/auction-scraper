/**
 * Auction Search Frontend
 * Connects to Supabase to search and display auction listings
 */

// ===== Supabase Configuration =====
// ===== Supabase Configuration =====
// Loaded from config.js


let supabaseClient;

// ===== State =====
const state = {
    currentPage: 1,
    pageSize: 24,
    totalCount: 0,
    searchQuery: '',
    startLot: null,
    auctionName: 'all',
    auctionDate: 'all',
    statusFilter: 'all',
    allAuctions: [], // Cache for loaded auctions
    vatFilter: 'all',
    sortBy: 'lot_number',
    isListView: false,
    showFavorites: false, // New state for tabs
    currentItems: []
};

// ===== DOM Elements =====
const elements = {
    searchInput: document.getElementById('searchInput'),
    clearBtn: document.getElementById('clearBtn'),
    searchBtn: document.getElementById('searchBtn'),
    startLot: document.getElementById('startLot'),
    auctionNameFilter: document.getElementById('auctionNameFilter'),
    auctionDateFilter: document.getElementById('auctionDateFilter'),
    statusFilter: document.getElementById('statusFilter'),
    vatFilter: document.getElementById('vatFilter'),
    sortBy: document.getElementById('sortBy'),
    resultsGrid: document.getElementById('resultsGrid'),
    resultsCount: document.getElementById('resultsCount'),
    loading: document.getElementById('loading'),
    emptyState: document.getElementById('emptyState'),
    pagination: document.getElementById('pagination'),
    prevBtn: document.getElementById('prevBtn'),
    nextBtn: document.getElementById('nextBtn'),
    pageInfo: document.getElementById('pageInfo'),
    totalLots: document.getElementById('totalLots'),
    totalValue: document.getElementById('totalValue'),
    modal: document.getElementById('itemModal'),
    modalBody: document.getElementById('modalBody'),
    modalClose: document.getElementById('modalClose'),
    modalClose: document.getElementById('modalClose'),
    viewBtns: document.querySelectorAll('.view-btn'),
    tabBtns: document.querySelectorAll('.tab-btn') // New
};

// ===== Initialize =====
async function init() {
    // Initialize Supabase client
    supabaseClient = window.supabase.createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY);

    // Load stats
    await loadStats();

    // Load auctions
    await loadAuctions();

    // Sync state from URL
    readURL();

    // Populate inputs from state (after URL read)
    populateInputs();

    // Initial search
    await performSearch(false, false); // Don't push state on initial load, don't scroll

    // Set up event listeners
    setupEventListeners();

    // Handle browser back/forward
    window.addEventListener('popstate', async () => {
        readURL();
        populateInputs();
        await performSearch(false, false);
    });
}

// ===== URL Management =====
function readURL() {
    const params = new URLSearchParams(window.location.search);

    state.currentPage = parseInt(params.get('page')) || 1;
    state.searchQuery = params.get('q') || '';
    state.startLot = params.get('start_lot') || null;
    state.auctionName = params.get('auction') || 'all';
    // If auction name is provided but date isn't, default to all. 
    // If both provided, use them.
    state.auctionDate = params.get('auction_id') || 'all';
    state.statusFilter = params.get('status') || 'all';
    state.vatFilter = params.get('vat') || 'all';
    state.sortBy = params.get('sort') || 'lot_number';

    // View preference (persisted via local storage or URL? URL is better for sharing)
    // But currently app.js has view toggles. Let's keep it simple for now or add to URL.
    // Let's add view to URL too.
    const view = params.get('view');
    if (view === 'list') {
        state.isListView = true;
    } else {
        state.isListView = false;
    }

    // Tab state
    const tab = params.get('tab');
    state.showFavorites = tab === 'favorites';
}

function updateURL(push = true) {
    const params = new URLSearchParams();

    if (state.currentPage > 1) params.set('page', state.currentPage);
    if (state.searchQuery) params.set('q', state.searchQuery);
    if (state.startLot) params.set('start_lot', state.startLot);
    if (state.auctionName !== 'all') params.set('auction', state.auctionName);
    if (state.auctionDate !== 'all') params.set('auction_id', state.auctionDate);
    if (state.statusFilter !== 'all') params.set('status', state.statusFilter);
    if (state.vatFilter !== 'all') params.set('vat', state.vatFilter);
    if (state.sortBy !== 'lot_number') params.set('sort', state.sortBy);
    if (state.isListView) params.set('view', 'list');
    if (state.showFavorites) params.set('tab', 'favorites');

    const newURL = `${window.location.pathname}?${params.toString()}`;

    if (push) {
        window.history.pushState({}, '', newURL);
    } else {
        window.history.replaceState({}, '', newURL);
    }
}

function populateInputs() {
    elements.searchInput.value = state.searchQuery;
    elements.clearBtn.style.display = state.searchQuery ? 'block' : 'none';

    elements.startLot.value = state.startLot || '';

    elements.auctionNameFilter.value = state.auctionName;
    populateDateFilter(); // Populate with all available dates
    elements.auctionDateFilter.value = state.auctionDate; // Set value after population

    elements.statusFilter.value = state.statusFilter;
    elements.vatFilter.value = state.vatFilter;
    elements.sortBy.value = state.sortBy;

    // Update view buttons
    elements.viewBtns.forEach(btn => {
        const isListBtn = btn.dataset.view === 'list';
        if ((state.isListView && isListBtn) || (!state.isListView && !isListBtn)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    elements.resultsGrid.classList.toggle('list-view', state.isListView);

    // Update tabs
    elements.tabBtns.forEach(btn => {
        const isFavTab = btn.dataset.tab === 'favorites';
        if ((state.showFavorites && isFavTab) || (!state.showFavorites && !isFavTab)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}


// ===== Event Listeners =====
function setupEventListeners() {
    // Search on button click
    elements.searchBtn.addEventListener('click', () => {
        state.currentPage = 1;
        updateStateFromInputs();
        performSearch();
    });

    // Date filter change
    elements.auctionDateFilter.addEventListener('change', () => {
        state.currentPage = 1;
        updateStateFromInputs();
        performSearch();
    });

    // Stats filters change
    elements.statusFilter.addEventListener('change', () => {
        state.currentPage = 1;
        updateStateFromInputs();
        performSearch();
    });

    // Other filters triggers
    // It's often better UX to trigger search on 'Enter' for inputs and change for selects
    // Or just use the main "Search" button for everything.
    // The previous code had listeners for individual filters. Let's keep that pattern for Selects.

    elements.vatFilter.addEventListener('change', () => {
        state.currentPage = 1;
        updateStateFromInputs();
        performSearch();
    });

    elements.sortBy.addEventListener('change', () => {
        state.currentPage = 1;
        updateStateFromInputs();
        performSearch();
    });

    // Search on Enter key
    elements.searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            state.currentPage = 1;
            updateStateFromInputs();
            performSearch();
        }
    });

    // Inputs: Min/Max/StartLot - Enter key trigger
    [elements.startLot].forEach(el => {
        el.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                state.currentPage = 1;
                updateStateFromInputs();
                performSearch();
            }
        });
    });

    // Show/hide clear button
    elements.searchInput.addEventListener('input', (e) => {
        elements.clearBtn.style.display = e.target.value ? 'block' : 'none';
    });

    // Clear search
    elements.clearBtn.addEventListener('click', () => {
        elements.searchInput.value = '';
        elements.clearBtn.style.display = 'none';
        state.currentPage = 1;
        updateStateFromInputs();
        performSearch();
    });

    // Pagination
    elements.prevBtn.addEventListener('click', () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            performSearch(); // updateURL handled inside
        }
    });

    elements.nextBtn.addEventListener('click', () => {
        const totalPages = Math.ceil(state.totalCount / state.pageSize);
        if (state.currentPage < totalPages) {
            state.currentPage++;
            performSearch();
        }
    });

    // View toggle
    elements.viewBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.viewBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.isListView = btn.dataset.view === 'list';
            elements.resultsGrid.classList.toggle('list-view', state.isListView);
            updateURL(false); // Update URL just for the view param, no push needed ideally but consistency is good
        });
    });

    // Hide Header on Scroll
    let lastScrollY = window.scrollY;
    const header = document.querySelector('.header');

    window.addEventListener('scroll', () => {
        const currentScrollY = window.scrollY;

        // Hide if scrolling down and past the header height (roughly 100px)
        if (currentScrollY > lastScrollY && currentScrollY > 100) {
            header.classList.add('hidden');
        } else {
            // Show if scrolling up
            header.classList.remove('hidden');
        }

        lastScrollY = currentScrollY;
    }, { passive: true });
};

// Tab switch
elements.tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        elements.tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.showFavorites = btn.dataset.tab === 'favorites';

        // Reset page to 1 on tab switch
        state.currentPage = 1;

        updateURL();
        performSearch();
    });
});

// Auction Filter Dependency
elements.auctionNameFilter.addEventListener('change', () => {
    state.auctionName = elements.auctionNameFilter.value;
    // Don't reset date filter anymore

    state.currentPage = 1;
    // Trigger search
    performSearch();
});

// Modal
elements.modalClose.addEventListener('click', closeModal);
elements.modal.querySelector('.modal-overlay').addEventListener('click', closeModal);
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});


function updateStateFromInputs() {
    state.searchQuery = elements.searchInput.value.trim();
    state.startLot = elements.startLot.value.trim() || null;
    state.auctionName = elements.auctionNameFilter.value;
    state.auctionDate = elements.auctionDateFilter.value;
    state.statusFilter = elements.statusFilter.value;
    state.vatFilter = elements.vatFilter.value;
    state.sortBy = elements.sortBy.value;
}

// ===== Load Stats =====
async function loadStats() {
    try {
        // Get total count
        const { count } = await supabaseClient
            .from('lots')
            .select('*', { count: 'exact', head: true });

        // Get total value
        const { data } = await supabaseClient
            .from('lots')
            .select('sold_price');

        const totalValue = data?.reduce((sum, lot) => sum + (lot.sold_price || 0), 0) || 0;

        elements.totalLots.textContent = count?.toLocaleString() || '0';
        elements.totalValue.textContent = `£${totalValue.toLocaleString()}`;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ===== Load Auctions =====
async function loadAuctions() {
    try {
        const { data, error } = await supabaseClient
            .from('auctions')
            .select('*')
            .order('scrape_date', { ascending: false });

        if (error) throw error;

        if (data) {
            state.allAuctions = data;

            // Extract unique names
            const names = new Set();
            data.forEach(a => {
                if (a.auction_name) names.add(a.auction_name);
                else names.add("Unnamed Auction");
            });

            elements.auctionNameFilter.innerHTML = '<option value="all">All Auctions</option>';

            // Sort names A-Z
            Array.from(names).sort().forEach(name => {
                const option = document.createElement('option');
                option.value = name;
                option.textContent = name;
                elements.auctionNameFilter.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading auctions:', error);
    }
}

// ===== Populate Date Filter =====
function populateDateFilter() {
    elements.auctionDateFilter.innerHTML = '<option value="all">All Dates</option>';

    // Get unique dates from all auctions
    const dates = new Map(); // timestamp -> display string

    state.allAuctions.forEach(auction => {
        if (!auction.scrape_date) return;

        const { dateStr, timestamp } = getWeekEndingDate(auction.scrape_date);

        if (!dates.has(timestamp)) {
            dates.set(timestamp, dateStr);
        }
    });

    // Sort descending
    const sortedDates = Array.from(dates.entries()).sort((a, b) => b[0] - a[0]);

    sortedDates.forEach(([timestamp, dateStr]) => {
        const option = document.createElement('option');
        // Use ISO string of the Saturday for filtering value
        option.value = new Date(timestamp).toISOString().split('T')[0];
        option.textContent = dateStr;
        elements.auctionDateFilter.appendChild(option);
    });
}

function getWeekEndingDate(dateString) {
    const date = new Date(dateString);
    const dayOfWeek = date.getDay();
    const daysUntilSat = 6 - dayOfWeek;
    const saturday = new Date(date);
    saturday.setDate(date.getDate() + daysUntilSat);

    // Set to noon to avoid timezone shift issues near midnight
    saturday.setHours(12, 0, 0, 0);

    return {
        dateStr: `Week ending ${saturday.toLocaleDateString('en-GB')}`,
        timestamp: saturday.getTime()
    };
}

// ===== Perform Search =====
async function performSearch(updateHistory = true, scroll = true) {
    if (updateHistory) {
        updateURL();
    }

    // Show loading
    elements.loading.style.display = 'block';
    elements.resultsGrid.innerHTML = '';
    elements.emptyState.style.display = 'none';
    elements.pagination.style.display = 'none';

    try {
        // Build query
        let query = supabaseClient
            .from('lots')
            .select('*', { count: 'exact' });

        // Text search
        if (state.searchQuery) {
            query = query.ilike('item_name', `%${state.searchQuery}%`);
        }

        // Start Lot filter
        if (state.startLot) {
            query = query.gte('lot_number', state.startLot);
        }

        // Auction & Date filtering
        // Logic: Find auction IDs that match BOTH the selected name and date
        if (state.auctionName !== 'all' || state.auctionDate !== 'all') {

            const relevantIds = state.allAuctions
                .filter(a => {
                    // Check Name
                    const nameMatch = state.auctionName === 'all' || (a.auction_name || "Unnamed Auction") === state.auctionName;

                    // Check Date
                    let dateMatch = true;
                    if (state.auctionDate !== 'all') {
                        if (!a.scrape_date) {
                            dateMatch = false;
                        } else {
                            const { timestamp } = getWeekEndingDate(a.scrape_date);
                            // Compare ISO date strings (YYY-MM-DD)
                            const satDate = new Date(timestamp).toISOString().split('T')[0];
                            dateMatch = satDate === state.auctionDate;
                        }
                    }

                    return nameMatch && dateMatch;
                })
                .map(a => a.id);

            if (relevantIds.length > 0) {
                query = query.in('auction_id', relevantIds);
            } else {
                // No auctions match the criteria
                query = query.eq('id', -1);
            }
        }


        // VAT filter
        if (state.vatFilter === 'vat') {
            query = query.eq('vat_applicable', true);
        } else if (state.vatFilter === 'no_vat') {
            query = query.eq('vat_applicable', false);
        }

        // Status filter
        if (state.statusFilter === 'sold') {
            query = query.not('hammer_price', 'is', null);
        } else if (state.statusFilter === 'not_sold') {
            query = query.is('hammer_price', null);
        } else if (state.statusFilter === 'not_sold') {
            query = query.is('hammer_price', null);
        }

        // Favorites filtering
        if (state.showFavorites) {
            query = query.eq('is_favourited', true);
        }

        // Sorting
        switch (state.sortBy) {
            case 'sold_price_asc':
                query = query.order('sold_price', { ascending: true });
                break;
            case 'sold_price_desc':
                query = query.order('sold_price', { ascending: false });
                break;
            case 'item_name':
                query = query.order('item_name', { ascending: true });
                break;
            default:
                // If using Start Lot, we definitely want to sort by lot number to make sense of the sequence
                query = query.order('lot_number', { ascending: true });
        }

        // Pagination
        const from = (state.currentPage - 1) * state.pageSize;
        const to = from + state.pageSize - 1;
        query = query.range(from, to);

        // Execute query
        const { data, count, error } = await query;

        if (error) throw error;

        state.totalCount = count || 0;
        state.currentItems = data || [];

        // Render results
        renderResults();

    } catch (error) {
        console.error('Search error:', error);
        elements.emptyState.querySelector('h3').textContent = 'Error loading results';
        elements.emptyState.querySelector('p').textContent = error.message;
        elements.emptyState.style.display = 'block';
    } finally {
        elements.loading.style.display = 'none';

        // Scroll to results if requested
        if (scroll && state.currentItems.length > 0) {
            const resultsSection = document.querySelector('.results-section');
            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }
}

// ===== Render Results =====
function renderResults() {
    // Update count
    elements.resultsCount.textContent = state.totalCount.toLocaleString();

    // Handle empty state
    if (state.currentItems.length === 0) {
        elements.emptyState.querySelector('h3').textContent = 'No results found';
        elements.emptyState.querySelector('p').textContent = 'Try adjusting your search terms or filters';
        elements.emptyState.style.display = 'block';
        return;
    }

    // Render items
    elements.resultsGrid.innerHTML = state.currentItems.map(item => `
        <article class="item-card" data-id="${item.id}">
            <div class="item-image-wrapper">
                ${item.image_url
            ? `<img class="item-image" src="${item.image_url}" alt="${escapeHtml(item.item_name)}" loading="lazy">`
            : `<div class="item-image-placeholder">📦</div>`
        }
                <button class="fav-btn ${item.is_favourited ? 'active' : ''}" 
                        data-id="${item.id}"
                        ${(item.hammer_price && !item.is_favourited) ? 'disabled title="Sold items cannot be favourited"' : 'title="Toggle Favourite"'}
                        onclick="event.stopPropagation(); toggleFavourite(${item.id}, this)">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                    </svg>
                </button>
            </div>
            <div class="item-content">
                <div class="item-lot">Lot #${item.lot_number}${item.vat_applicable ? ' <span class="vat-badge">+VAT</span>' : ''}</div>
                <h3 class="item-name">${escapeHtml(item.item_name || 'Untitled Item')}</h3>
                <div class="item-prices">
                    <div class="price-hammer"><span class="price-type">Hammer:</span> £${item.hammer_price?.toLocaleString() || '0'}</div>
                    <div class="price-breakdown">
                        <span class="price-label">Total: £${item.price_total?.toLocaleString() || item.hammer_price?.toLocaleString() || '0'}</span>
                    </div>
                </div>
            </div>
        </article>
    `).join('');

    // Add click handlers to cards
    elements.resultsGrid.querySelectorAll('.item-card').forEach(card => {
        card.addEventListener('click', () => {
            const item = state.currentItems.find(i => i.id == card.dataset.id);
            if (item) openModal(item);
        });
    });

    // Update pagination
    const totalPages = Math.ceil(state.totalCount / state.pageSize);
    elements.pagination.style.display = totalPages > 1 ? 'flex' : 'none';
    elements.prevBtn.disabled = state.currentPage <= 1;
    elements.nextBtn.disabled = state.currentPage >= totalPages;
    elements.pageInfo.textContent = `Page ${state.currentPage} of ${totalPages}`;
}

// ===== Modal =====
function openModal(item) {
    elements.modalBody.innerHTML = `
        ${item.image_url
            ? `<img class="modal-image" src="${item.image_url}" alt="${escapeHtml(item.item_name)}">`
            : ''
        }
        <div class="modal-details">
            <div class="modal-lot">Lot #${item.lot_number}${item.vat_applicable ? ' <span class="vat-badge">+VAT</span>' : ''}</div>
            <h2 class="modal-name">${escapeHtml(item.item_name || 'Untitled Item')}</h2>
            <div class="modal-prices">
                <div class="modal-price-row">
                    <span class="price-label">Hammer Price:</span>
                    <span class="price-value">£${item.hammer_price?.toLocaleString() || '0'}</span>
                </div>
                <div class="modal-price-row">
                    <span class="price-label">+ Buyer's Premium (21%):</span>
                    <span class="price-value">£${item.price_with_premium?.toLocaleString() || '0'}</span>
                </div>
                ${item.vat_applicable ? `
                <div class="modal-price-row">
                    <span class="price-label">+ VAT (20%):</span>
                    <span class="price-value">£${item.price_total?.toLocaleString() || '0'}</span>
                </div>
                ` : ''}
                <div class="modal-price-total">
                    <span>Total:</span>
                    <span>£${item.price_total?.toLocaleString() || item.price_with_premium?.toLocaleString() || '0'}</span>
                </div>
            </div>
        </div>
    `;
    elements.modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    elements.modal.classList.remove('active');
    document.body.style.overflow = '';
}

// ===== Toggle Favourite =====
async function toggleFavourite(id, btn) {
    // Check if button is disabled (shouldn't fire due to attribute, but double check)
    if (btn.disabled) return;

    // Check if item is sold - we only allow UN-favouriting if sold
    const item = state.currentItems.find(i => i.id === id);
    if (item && item.hammer_price && !item.is_favourited) {
        alert('Sold items cannot be favourited.');
        return;
    }

    const isActive = btn.classList.contains('active');
    const newState = !isActive;

    // Optimistic UI update
    btn.classList.toggle('active', newState);

    try {
        const { error } = await supabaseClient
            .from('lots')
            .update({ is_favourited: newState })
            .eq('id', id);

        if (error) throw error;

        // Update local state so it persists if we re-render
        if (item) {
            item.is_favourited = newState;
        }

    } catch (error) {
        console.error('Error toggling favourite:', error);
        // Revert UI on error
        btn.classList.toggle('active', isActive);
        alert('Failed to update favourite status. Please try again.');
    }
}

// ===== Utilities =====
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== Start App =====
document.addEventListener('DOMContentLoaded', init);
