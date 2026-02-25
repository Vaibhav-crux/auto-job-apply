/**
 * Applied Jobs Viewer — Frontend Logic
 * Handles tabs, data fetching, card rendering, search, pagination, and empty states.
 */

const API_BASE = "";  // same origin
let currentTab = "";
let allGroups = [];       // current tab's job groups (date → jobs)
let allFlatJobs = [];     // flattened list of all jobs (for pagination + search)
let filteredJobs = [];    // after search filter
let currentPage = 1;
let pageSize = 20;

// DOM elements
const tabsContainer = document.getElementById("tabsContainer");
const loader = document.getElementById("loader");
const emptyState = document.getElementById("emptyState");
const emptyMessage = document.getElementById("emptyMessage");
const jobsContainer = document.getElementById("jobsContainer");
const searchInput = document.getElementById("searchInput");
const searchCount = document.getElementById("searchCount");
const statsBar = document.getElementById("statsBar");
const totalJobsEl = document.getElementById("totalJobs");
const totalDatesEl = document.getElementById("totalDates");
const paginationContainer = document.getElementById("paginationContainer");
const pageSizeSelect = document.getElementById("pageSizeSelect");


// ── Init ────────────────────────────────────────
async function init() {
    showLoader();

    // Page size selector
    pageSizeSelect.addEventListener("change", () => {
        pageSize = parseInt(pageSizeSelect.value);
        currentPage = 1;
        renderCurrentView();
    });

    try {
        const res = await fetch(`${API_BASE}/api/tabs`);
        const data = await res.json();
        renderTabs(data.tabs, data.default);

        const defaultTab = data.tabs.includes(data.default) ? data.default : data.tabs[0];
        if (defaultTab) {
            await switchTab(defaultTab);
        } else {
            showEmpty("No job folders found in excels/ directory.");
        }
    } catch (err) {
        showEmpty("Failed to connect to server. Run: python serve_frontend.py");
        console.error(err);
    }
}


// ── Tabs ────────────────────────────────────────
function renderTabs(tabs, defaultTab) {
    tabsContainer.innerHTML = "";
    tabs.forEach(tab => {
        const btn = document.createElement("button");
        btn.className = "tab-btn";
        btn.textContent = toTitleCase(tab);
        btn.dataset.tab = tab;
        btn.addEventListener("click", () => switchTab(tab));
        tabsContainer.appendChild(btn);
    });
}

async function switchTab(tabName) {
    currentTab = tabName;

    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.tab === tabName);
    });

    searchInput.value = "";
    searchCount.textContent = "";
    currentPage = 1;

    showLoader();

    try {
        const res = await fetch(`${API_BASE}/api/jobs/${tabName}`);
        const data = await res.json();

        if (data.error) {
            showEmpty(data.error);
            return;
        }

        allGroups = data.groups || [];

        // Flatten all jobs for pagination/search (preserve date info)
        allFlatJobs = [];
        allGroups.forEach(group => {
            group.jobs.forEach(job => {
                job._date = group.date;
                allFlatJobs.push(job);
            });
        });

        if (allFlatJobs.length === 0) {
            showEmpty(`No applied jobs found in "${toTitleCase(tabName)}" folder.`);
            return;
        }

        filteredJobs = allFlatJobs;
        renderCurrentView();
    } catch (err) {
        showEmpty("Error loading jobs. Check server is running.");
        console.error(err);
    }
}


// ── Render Current View (pagination-aware) ───────
function renderCurrentView() {
    const totalItems = filteredJobs.length;
    const totalPages = Math.ceil(totalItems / pageSize);

    if (currentPage > totalPages) currentPage = totalPages || 1;

    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, totalItems);
    const pageJobs = filteredJobs.slice(startIdx, endIdx);

    // Group page jobs by date
    const groupedByDate = [];
    const dateMap = {};
    pageJobs.forEach(job => {
        const date = job._date || "Unknown Date";
        if (!dateMap[date]) {
            dateMap[date] = { date, jobs: [] };
            groupedByDate.push(dateMap[date]);
        }
        dateMap[date].jobs.push(job);
    });

    renderJobs(groupedByDate, totalItems);
    renderPagination(totalPages);
}


// ── Render Jobs ─────────────────────────────────
function renderJobs(groups, totalItems) {
    jobsContainer.innerHTML = "";

    groups.forEach((group, groupIdx) => {
        const section = document.createElement("div");
        section.className = "date-group";
        section.style.animationDelay = `${groupIdx * 0.05}s`;

        const jobCount = group.jobs.length;

        section.innerHTML = `
            <div class="date-header">
                <span class="date-label">📅 ${group.date}</span>
                <span class="date-count">${jobCount} job${jobCount !== 1 ? "s" : ""}</span>
                <div class="date-divider"></div>
            </div>
        `;

        const grid = document.createElement("div");
        grid.className = "cards-grid";

        group.jobs.forEach(job => {
            grid.appendChild(createJobCard(job));
        });

        section.appendChild(grid);
        jobsContainer.appendChild(section);
    });

    // Unique dates across ALL filtered jobs (not just current page)
    const uniqueDates = new Set(filteredJobs.map(j => j._date));

    loader.style.display = "none";
    emptyState.style.display = "none";
    jobsContainer.style.display = "block";
    statsBar.style.display = "flex";

    totalJobsEl.textContent = `${totalItems} applied`;
    totalDatesEl.textContent = `${uniqueDates.size} day${uniqueDates.size !== 1 ? "s" : ""}`;
}

function createJobCard(job) {
    const card = document.createElement("div");
    card.className = "job-card";

    const position = job["Position"] || "";
    const company = job["Company"] || "";
    const location = job["Location"] || "";
    const experience = job["Experience"] || "";
    const salary = job["Salary"] || "";
    const skills = job["Skills"] || "";
    const link = job["Link"] || "";
    const time = job["time"] || "";

    card.dataset.searchText = `${position} ${company} ${location} ${experience} ${salary} ${skills}`.toLowerCase();

    // Position with link
    const positionHTML = link
        ? `<a href="${escapeHTML(link)}" target="_blank" rel="noopener">${escapeHTML(position)}</a>`
        : escapeHTML(position);

    // Link icon (external link button)
    const linkIconHTML = link
        ? `<a href="${escapeHTML(link)}" target="_blank" rel="noopener" class="card-link-icon" title="Open job listing">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
               <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
               <polyline points="15 3 21 3 21 9"></polyline>
               <line x1="10" y1="14" x2="21" y2="3"></line>
             </svg>
           </a>`
        : "";

    // Meta chips
    let metaHTML = "";
    if (location) {
        metaHTML += `<span class="meta-chip"><span class="chip-icon">📍</span>${escapeHTML(location)}</span>`;
    }
    if (experience) {
        metaHTML += `<span class="meta-chip"><span class="chip-icon">💼</span>${escapeHTML(experience)}</span>`;
    }
    if (salary) {
        metaHTML += `<span class="meta-chip"><span class="chip-icon">💰</span>${escapeHTML(salary)}</span>`;
    }

    // Skills tags
    let skillsHTML = "";
    if (skills) {
        const skillList = skills.split(",").map(s => s.trim()).filter(s => s);
        skillsHTML = skillList.map(s => `<span class="skill-tag">${escapeHTML(s)}</span>`).join("");
    }

    // Company search icon (Google)
    const googleSearchURL = company
        ? `https://www.google.com/search?q=${encodeURIComponent(company + " Company")}`
        : "";
    const companySearchHTML = company && googleSearchURL
        ? `<a href="${escapeHTML(googleSearchURL)}" target="_blank" rel="noopener" class="company-search-icon" title="Search ${escapeHTML(company)} on Google">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
               <circle cx="11" cy="11" r="8"></circle>
               <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
             </svg>
           </a>`
        : "";

    card.innerHTML = `
        <div class="card-top">
            <div class="card-position">${positionHTML}</div>
            <div class="card-top-right">
                ${time ? `<span class="card-time">${escapeHTML(time)}</span>` : ""}
                ${linkIconHTML}
            </div>
        </div>
        <div class="card-company">${escapeHTML(company)}${companySearchHTML}</div>
        ${metaHTML ? `<div class="card-meta">${metaHTML}</div>` : ""}
        ${skillsHTML ? `<div class="card-skills">${skillsHTML}</div>` : ""}
    `;

    return card;
}


// ── Pagination ──────────────────────────────────
function renderPagination(totalPages) {
    paginationContainer.innerHTML = "";

    if (totalPages <= 1) {
        paginationContainer.style.display = "none";
        return;
    }

    paginationContainer.style.display = "flex";

    const PAGES_PER_GROUP = 10;
    const currentGroup = Math.floor((currentPage - 1) / PAGES_PER_GROUP);
    const groupStart = currentGroup * PAGES_PER_GROUP + 1;
    const groupEnd = Math.min(groupStart + PAGES_PER_GROUP - 1, totalPages);

    // << Previous group
    if (groupStart > 1) {
        const prevBtn = createPageBtn("«", () => {
            currentPage = groupStart - 1;
            renderCurrentView();
            scrollToTop();
        });
        prevBtn.classList.add("page-nav");
        prevBtn.title = `Pages ${groupStart - PAGES_PER_GROUP}–${groupStart - 1}`;
        paginationContainer.appendChild(prevBtn);
    }

    // Page numbers
    for (let i = groupStart; i <= groupEnd; i++) {
        const btn = createPageBtn(i, () => {
            currentPage = i;
            renderCurrentView();
            scrollToTop();
        });
        if (i === currentPage) btn.classList.add("active");
        paginationContainer.appendChild(btn);
    }

    // >> Next group
    if (groupEnd < totalPages) {
        const nextBtn = createPageBtn("»", () => {
            currentPage = groupEnd + 1;
            renderCurrentView();
            scrollToTop();
        });
        nextBtn.classList.add("page-nav");
        nextBtn.title = `Pages ${groupEnd + 1}–${Math.min(groupEnd + PAGES_PER_GROUP, totalPages)}`;
        paginationContainer.appendChild(nextBtn);
    }
}

function createPageBtn(label, onClick) {
    const btn = document.createElement("button");
    btn.className = "page-btn";
    btn.textContent = label;
    btn.addEventListener("click", onClick);
    return btn;
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
}


// ── Search ──────────────────────────────────────
searchInput.addEventListener("input", debounce(handleSearch, 200));

function handleSearch() {
    const query = searchInput.value.trim().toLowerCase();

    if (!query) {
        filteredJobs = allFlatJobs;
        searchCount.textContent = "";
    } else {
        const terms = query.split(/\s+/);
        filteredJobs = allFlatJobs.filter(job => {
            const text = `${job["Position"] || ""} ${job["Company"] || ""} ${job["Location"] || ""} ${job["Experience"] || ""} ${job["Salary"] || ""} ${job["Skills"] || ""}`.toLowerCase();
            return terms.every(term => text.includes(term));
        });
        searchCount.textContent = `${filteredJobs.length} result${filteredJobs.length !== 1 ? "s" : ""}`;
    }

    currentPage = 1;

    if (filteredJobs.length === 0 && query) {
        jobsContainer.style.display = "none";
        paginationContainer.style.display = "none";
        emptyState.style.display = "block";
        emptyMessage.textContent = `No results for "${query}"`;
        statsBar.style.display = "none";
    } else if (filteredJobs.length === 0) {
        showEmpty("No applied jobs found.");
    } else {
        emptyState.style.display = "none";
        renderCurrentView();
    }
}


// ── UI Helpers ───────────────────────────────────
function showLoader() {
    loader.style.display = "flex";
    emptyState.style.display = "none";
    jobsContainer.style.display = "none";
    statsBar.style.display = "none";
    paginationContainer.style.display = "none";
}

function showEmpty(message) {
    loader.style.display = "none";
    emptyState.style.display = "block";
    jobsContainer.style.display = "none";
    statsBar.style.display = "none";
    paginationContainer.style.display = "none";
    emptyMessage.textContent = message || "No applied jobs data in this folder yet.";
}


// ── Utilities ────────────────────────────────────
function toTitleCase(str) {
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function debounce(fn, ms) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), ms);
    };
}


// ── Start ────────────────────────────────────────
document.addEventListener("DOMContentLoaded", init);
