const API_BASE = "http://localhost:8000";

let revenueChart;
let productChart;

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

function renderCharts(stats) {
  const revenueCtx = document.getElementById("revenueChart").getContext("2d");
  const productCtx = document.getElementById("productChart").getContext("2d");

  if (revenueChart) {
    revenueChart.destroy();
  }
  if (productChart) {
    productChart.destroy();
  }

  revenueChart = new Chart(revenueCtx, {
    type: "line",
    data: {
      labels: stats.revenue_labels,
      datasets: [
        {
          label: "Revenue ($M)",
          data: stats.revenue_millions,
          borderColor: "#e76f51",
          backgroundColor: "rgba(231,111,81,0.16)",
          fill: true,
          tension: 0.34,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: true } },
    },
  });

  productChart = new Chart(productCtx, {
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
  });
}

async function initializeDashboard() {
  try {
    const stats = await fetchStats();
    renderKpis(stats);
    renderCharts(stats);
  } catch (error) {
    document.getElementById("analysisResult").textContent = `Dashboard init error: ${error.message}`;
  }
}

async function onAnalyzeSubmit(event) {
  event.preventDefault();
  const resultNode = document.getElementById("analysisResult");
  resultNode.classList.remove("success");
  resultNode.textContent = "Running analysis...";

  const query = document.getElementById("query").value.trim();
  const contextQuery = document.getElementById("contextQuery").value.trim();

  try {
    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        context_query: contextQuery.length ? contextQuery : null,
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
