const API_BASE = "http://localhost:8000";

let revenueChart;
let productChart;
let csvDistributionChart;
let currentRevenueType = "line";
let currentProductType = "doughnut";
let currentPeriod = "monthly";
let currentStats = null;

// ============= UTILITY FUNCTIONS =============

function generatePeriodData(period) {
  const baseLabels = {
    weekly: ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"],
    monthly: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    quarterly: ["Q1", "Q2", "Q3", "Q4"],
  };

  const baseRevenue = {
    weekly: [120, 145, 138, 165, 158, 172, 190, 205],
    monthly: [450, 520, 480, 590, 640, 710],
    quarterly: [1450, 1720, 1950, 2150],
  };

  return {
    labels: baseLabels[period],
    data: baseRevenue[period],
  };
}

function generateChartConfig(type, labels, data, title = "") {
  const colors = {
    line: {
      border: "#e76f51",
      background: "rgba(231,111,81,0.16)",
    },
    bar: {
      background: "#e76f51",
    },
    area: {
      border: "#e76f51",
      background: "rgba(231,111,81,0.3)",
    },
  };

  const configs = {
    line: {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: title || "Revenue ($M)",
            data,
            borderColor: colors.line.border,
            backgroundColor: colors.line.background,
            fill: true,
            tension: 0.34,
            pointRadius: 5,
            pointHoverRadius: 7,
            pointBackgroundColor: colors.line.border,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: "#5b5b5b" },
            grid: { color: "rgba(215,209,198,0.3)" },
          },
          x: { ticks: { color: "#5b5b5b" } },
        },
      },
    },
    bar: {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: title || "Revenue ($M)",
            data,
            backgroundColor: colors.bar.background,
            borderRadius: 8,
            borderSkipped: false,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: "#5b5b5b" },
            grid: { color: "rgba(215,209,198,0.3)" },
          },
          x: { ticks: { color: "#5b5b5b" } },
        },
      },
    },
    area: {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: title || "Revenue ($M)",
            data,
            borderColor: colors.area.border,
            backgroundColor: colors.area.background,
            fill: true,
            tension: 0.4,
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: "#5b5b5b" },
            grid: { color: "rgba(215,209,198,0.3)" },
          },
          x: { ticks: { color: "#5b5b5b" } },
        },
      },
    },
  };

  return configs[type];
}

// ============= CHART RENDERING =============

async function fetchStats() {
  const response = await fetch(`${API_BASE}/api/stats`);
  if (!response.ok) {
    throw new Error("Failed to fetch stats");
  }
  return response.json();
}

function renderKpis(stats) {
  const totalRevenue = stats.revenue_millions.reduce((acc, x) => acc + x, 0);
  document.getElementById("revenueTotal").textContent = `$${totalRevenue.toFixed(1)}M`;
  document.getElementById("indexedSources").textContent = String(stats.total_sources);
}

function updateKpisForPeriod(total, count) {
  // Update KPIs with provided values
  const periodLabel = currentPeriod.charAt(0).toUpperCase() + currentPeriod.slice(1);
  
  const revenueTrendLabel = document.getElementById("revenueTrendLabel");
  const revenueTotal = document.getElementById("revenueTotal");
  const indexedSources = document.getElementById("indexedSources");
  
  if (revenueTrendLabel) revenueTrendLabel.textContent = `Revenue (${periodLabel})`;
  if (revenueTotal) revenueTotal.textContent = `$${total}M`;
  if (indexedSources) indexedSources.textContent = `${count} ${periodLabel}s`;
}

function renderRevenueChart(stats) {
  const periodData = generatePeriodData(currentPeriod);
  const config = generateChartConfig(currentRevenueType, periodData.labels, periodData.data, "Revenue ($M)");

  const revenueCtx = document.getElementById("revenueChart").getContext("2d");
  
  if (revenueChart) {
    revenueChart.destroy();
  }

  revenueChart = new Chart(revenueCtx, config);

  // Calculate statistics
  const total = periodData.data.reduce((a, b) => a + b, 0);
  const avg = (total / periodData.data.length).toFixed(1);
  const max = Math.max(...periodData.data);
  const min = Math.min(...periodData.data);

  // Update KPI cards directly
  const periodLabel = currentPeriod.charAt(0).toUpperCase() + currentPeriod.slice(1);
  const revenueTrendLabel = document.getElementById("revenueTrendLabel");
  const revenueTotal = document.getElementById("revenueTotal");
  const indexedSources = document.getElementById("indexedSources");
  
  if (revenueTrendLabel) revenueTrendLabel.textContent = `Revenue (${periodLabel})`;
  if (revenueTotal) revenueTotal.textContent = `$${total}M`;
  if (indexedSources) indexedSources.textContent = `${periodData.labels.length} ${periodLabel}s`;

  // Update stats below chart
  const statsHtml = `
    <div class="stat-item">
      <span class="stat-label">Total</span>
      <span class="stat-value">$${total}M</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Average</span>
      <span class="stat-value">$${avg}M</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Max</span>
      <span class="stat-value">$${max}M</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Min</span>
      <span class="stat-value">$${min}M</span>
    </div>
  `;
  document.getElementById("revenueStats").innerHTML = statsHtml;
}

function renderProductChart(stats) {
  const productCtx = document.getElementById("productChart").getContext("2d");

  if (productChart) {
    productChart.destroy();
  }

  const chartConfigs = {
    doughnut: {
      type: "doughnut",
      data: {
        labels: Object.keys(stats.product_share),
        datasets: [
          {
            data: Object.values(stats.product_share),
            backgroundColor: ["#2a9d8f", "#e9c46a", "#f4a261"],
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
      },
    },
    pie: {
      type: "pie",
      data: {
        labels: Object.keys(stats.product_share),
        datasets: [
          {
            data: Object.values(stats.product_share),
            backgroundColor: ["#2a9d8f", "#e9c46a", "#f4a261"],
            borderWidth: 2,
            borderColor: "#fffef9",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
      },
    },
    bar: {
      type: "bar",
      data: {
        labels: Object.keys(stats.product_share),
        datasets: [
          {
            label: "Revenue Share (%)",
            data: Object.values(stats.product_share),
            backgroundColor: ["#2a9d8f", "#e9c46a", "#f4a261"],
            borderRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        indexAxis: "y",
        plugins: { legend: { display: true } },
        scales: {
          x: { beginAtZero: true, max: 100 },
        },
      },
    },
  };

  productChart = new Chart(productCtx, chartConfigs[currentProductType]);
}

async function initializeDashboard() {
  try {
    currentStats = await fetchStats();
    renderRevenueChart(currentStats);
    renderProductChart(currentStats);
  } catch (error) {
    document.getElementById("analysisResult").textContent = `Dashboard init error: ${error.message}`;
  }
}

// ============= CHART CONTROLS =============

// Chart type button handlers - Fixed version
document.addEventListener("DOMContentLoaded", function() {
  // Revenue chart type buttons
  const revenueCard = document.querySelector("#revenueChart").closest(".card");
  if (revenueCard) {
    revenueCard.querySelectorAll('[data-chart]').forEach((btn) => {
      btn.addEventListener("click", function () {
        revenueCard.querySelectorAll('[data-chart]').forEach((b) => b.classList.remove("active"));
        this.classList.add("active");
        currentRevenueType = this.dataset.chart;
        renderRevenueChart(currentStats);
      });
    });
  }

  // Product chart type buttons
  const productCard = document.querySelector("#productChart").closest(".card");
  if (productCard) {
    productCard.querySelectorAll('[data-chart]').forEach((btn) => {
      btn.addEventListener("click", function () {
        productCard.querySelectorAll('[data-chart]').forEach((b) => b.classList.remove("active"));
        this.classList.add("active");
        currentProductType = this.dataset.chart;
        renderProductChart(currentStats);
      });
    });
  }
});

// Period selector
document.getElementById("periodSelector").addEventListener("change", function () {
  currentPeriod = this.value;
  renderRevenueChart(currentStats);
});

// Export buttons
document.getElementById("exportRevenueBtn").addEventListener("click", function () {
  if (revenueChart) {
    const url = revenueChart.toBase64Image();
    const link = document.createElement("a");
    link.href = url;
    link.download = `revenue-chart-${new Date().toISOString().slice(0, 10)}.png`;
    link.click();
  }
});

document.getElementById("exportProductBtn").addEventListener("click", function () {
  if (productChart) {
    const url = productChart.toBase64Image();
    const link = document.createElement("a");
    link.href = url;
    link.download = `product-chart-${new Date().toISOString().slice(0, 10)}.png`;
    link.click();
  }
});

// ============= CSV ANALYSIS =============

document.getElementById("analyzeCsvBtn").addEventListener("click", async function () {
  const fileSelect = document.getElementById("csvFileSelect");
  const selectedFile = fileSelect.value;
  const resultNode = document.getElementById("csvAnalysisResult");

  if (!selectedFile) {
    resultNode.textContent = "Please select a CSV file first.";
    return;
  }

  resultNode.textContent = "📊 Analyzing file...";

  try {
    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: `Provide a comprehensive analysis of ${selectedFile}. Include: 1) Row and column count, 2) Data types of each column, 3) Any missing values, 4) Basic statistics (min, max, mean for numeric columns), 5) Key insights`,
        context_query: selectedFile,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Analysis failed");
    }

    resultNode.classList.add("success");
    resultNode.textContent = data.response;

    // Show generated charts
    generateCsvCharts(selectedFile);
  } catch (error) {
    resultNode.classList.remove("success");
    resultNode.textContent = `Analysis error: ${error.message}`;
  }
});

function generateCsvCharts(filename) {
  // Sample data for demonstration - in production, get from backend
  const distributionData = {
    labels: ["Category A", "Category B", "Category C", "Category D"],
    values: [35, 25, 20, 20],
  };

  const container = document.getElementById("csvChartsContainer");
  container.style.display = "grid";

  const ctx = document.getElementById("csvDistributionChart").getContext("2d");
  if (csvDistributionChart) {
    csvDistributionChart.destroy();
  }

  csvDistributionChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: distributionData.labels,
      datasets: [
        {
          label: "Distribution",
          data: distributionData.values,
          backgroundColor: ["#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"],
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: true } },
    },
  });

  // Update summary stats
  const summaryHtml = `
    <div class="summary-card">
      <div class="summary-card-title">Total Records</div>
      <div class="summary-card-value">1,250</div>
    </div>
    <div class="summary-card">
      <div class="summary-card-title">Columns</div>
      <div class="summary-card-value">8</div>
    </div>
    <div class="summary-card">
      <div class="summary-card-title">Missing Values</div>
      <div class="summary-card-value">3</div>
    </div>
    <div class="summary-card">
      <div class="summary-card-title">Data Quality</div>
      <div class="summary-card-value">99.7%</div>
    </div>
  `;
  document.getElementById("csvSummaryStats").innerHTML = summaryHtml;
}

// ============= EXISTING ANALYZE & INGEST =============

async function onAnalyzeSubmit(event) {
  event.preventDefault();
  const resultNode = document.getElementById("analysisResult");
  resultNode.classList.remove("success");
  resultNode.textContent = "Running analysis...";

  const query = document.getElementById("query").value.trim();
  const contextQuery = document.getElementById("contextQuery").value.trim();
  const selectedFile = document.getElementById("agentFileSelect").value.trim();

  try {
    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        context_query: contextQuery.length ? contextQuery : null,
        file: selectedFile.length ? selectedFile : null,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Analysis failed");
    }

    resultNode.classList.add("success");
    resultNode.textContent = data.response;
  } catch (error) {
    resultNode.textContent = `Analysis error: ${error.message}`;
  }
}

async function onIngestSubmit(event) {
  event.preventDefault();
  const resultNode = document.getElementById("ingestResult");
  resultNode.classList.remove("success");

  const fileInput = document.getElementById("fileInput");
  if (!fileInput.files.length) {
    resultNode.textContent = "Please select a file first.";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  resultNode.textContent = "Uploading and ingesting...";

  try {
    const response = await fetch(`${API_BASE}/api/ingest`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Ingestion failed");
    }

    resultNode.classList.add("success");
    resultNode.textContent = `Ingested ${data.loaded_documents} document(s) from ${data.file}`;
    await initializeDashboard();
  } catch (error) {
    resultNode.textContent = `Ingestion error: ${error.message}`;
  }
}

document.getElementById("analyzeForm").addEventListener("submit", onAnalyzeSubmit);
document.getElementById("ingestForm").addEventListener("submit", onIngestSubmit);

initializeDashboard();
