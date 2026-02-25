/**
 * Applied Jobs Viewer — Frontend Logic
 * Handles tabs, data fetching, card rendering, search, and empty states.
 */

const API_BASE = "";  // same origin
let currentTab = "";
let allGroups = [];  // current tab's job groups (date → jobs)

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


// ── Init ────────────────────────────────────────
async function init() {
    showLoader();
    try {
        const res = await fetch(`${API_BASE}/api/tabs`);
        const data = await res.json();
        renderTabs(data.tabs, data.default);

        // Load default tab
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

    // Update active tab styling
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.tab === tabName);
    });

    // Clear search
    searchInput.value = "";
    searchCount.textContent = "";

    showLoader();

    try {
        const res = await fetch(`${API_BASE}/api/jobs/${tabName}`);
        const data = await res.json();

        if (data.error) {
            showEmpty(data.error);
            return;
        }

        allGroups = data.groups || [];

        if (allGroups.length === 0) {
            showEmpty(`No applied jobs found in "${toTitleCase(tabName)}" folder.`);
            return;
        }

        renderJobs(allGroups);
    } catch (err) {
        showEmpty("Error loading jobs. Check server is running.");
        console.error(err);
    }
}


// ── Render Jobs ─────────────────────────────────
function renderJobs(groups) {
    jobsContainer.innerHTML = "";
    let totalJobs = 0;

    groups.forEach((group, groupIdx) => {
        const section = document.createElement("div");
        section.className = "date-group";
        section.dataset.date = group.date;
        section.style.animationDelay = `${groupIdx * 0.05}s`;

        const jobCount = group.jobs.length;
        totalJobs += jobCount;

        // Date header
        section.innerHTML = `
            <div class="date-header">
                <span class="date-label">📅 ${group.date}</span>
                <span class="date-count">${jobCount} job${jobCount !== 1 ? "s" : ""}</span>
                <div class="date-divider"></div>
            </div>
        `;

        // Cards grid
        const grid = document.createElement("div");
        grid.className = "cards-grid";

        group.jobs.forEach(job => {
            grid.appendChild(createJobCard(job));
        });

        section.appendChild(grid);
        jobsContainer.appendChild(section);
    });

    // Show container, update stats
    loader.style.display = "none";
    emptyState.style.display = "none";
    jobsContainer.style.display = "block";
    statsBar.style.display = "flex";

    totalJobsEl.textContent = `${totalJobs} job${totalJobs !== 1 ? "s" : ""}`;
    totalDatesEl.textContent = `${groups.length} day${groups.length !== 1 ? "s" : ""}`;
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

    // Searchable text (stored as data attribute)
    card.dataset.searchText = `${position} ${company} ${location} ${experience} ${salary} ${skills}`.toLowerCase();

    // Position (with link if available)
    const positionHTML = link
        ? `<a href="${escapeHTML(link)}" target="_blank" rel="noopener">${escapeHTML(position)}</a>`
        : escapeHTML(position);

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

    card.innerHTML = `
        <div class="card-top">
            <div class="card-position">${positionHTML}</div>
            ${time ? `<span class="card-time">${escapeHTML(time)}</span>` : ""}
        </div>
        <div class="card-company">${escapeHTML(company)}</div>
        ${metaHTML ? `<div class="card-meta">${metaHTML}</div>` : ""}
        ${skillsHTML ? `<div class="card-skills">${skillsHTML}</div>` : ""}
    `;

    return card;
}


// ── Search ──────────────────────────────────────
searchInput.addEventListener("input", debounce(handleSearch, 200));

function handleSearch() {
    const query = searchInput.value.trim().toLowerCase();

    if (!query) {
        // Reset: show all cards, remove highlights
        document.querySelectorAll(".job-card").forEach(card => card.classList.remove("hidden"));
        document.querySelectorAll(".date-group").forEach(group => group.classList.remove("hidden"));
        searchCount.textContent = "";
        updateDateCounts();
        return;
    }

    const terms = query.split(/\s+/);
    let visibleCount = 0;

    document.querySelectorAll(".job-card").forEach(card => {
        const text = card.dataset.searchText;
        const matches = terms.every(term => text.includes(term));
        card.classList.toggle("hidden", !matches);
        if (matches) visibleCount++;
    });

    // Hide empty date groups
    document.querySelectorAll(".date-group").forEach(group => {
        const visibleCards = group.querySelectorAll(".job-card:not(.hidden)");
        group.classList.toggle("hidden", visibleCards.length === 0);
    });

    searchCount.textContent = `${visibleCount} result${visibleCount !== 1 ? "s" : ""}`;
    updateDateCounts();
}

function updateDateCounts() {
    document.querySelectorAll(".date-group").forEach(group => {
        const visibleCards = group.querySelectorAll(".job-card:not(.hidden)").length;
        const countEl = group.querySelector(".date-count");
        if (countEl) {
            countEl.textContent = `${visibleCards} job${visibleCards !== 1 ? "s" : ""}`;
        }
    });
}


// ── UI Helpers ───────────────────────────────────
function showLoader() {
    loader.style.display = "flex";
    emptyState.style.display = "none";
    jobsContainer.style.display = "none";
    statsBar.style.display = "none";
}

function showEmpty(message) {
    loader.style.display = "none";
    emptyState.style.display = "block";
    jobsContainer.style.display = "none";
    statsBar.style.display = "none";
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
