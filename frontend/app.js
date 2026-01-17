const statusEl = document.getElementById("status");
const productSelect = document.getElementById("productSelect");
const mortalityFileSelect = document.getElementById("mortalityFile");
const sheetNameInput = document.getElementById("sheetName");
const uploadBtn = document.getElementById("uploadBtn");
const fileUpload = document.getElementById("fileUpload");
const runBtn = document.getElementById("runBtn");
const summaryCards = document.getElementById("summaryCards");
const newProductRow = document.getElementById("newProductRow");
const newProductNameInput = document.getElementById("newProductName");
const saveProductBtn = document.getElementById("saveProductBtn");
const targetMarginInput = document.getElementById("targetMargin");
const optimizeBtn = document.getElementById("optimizeBtn");
const sensitivityBtn = document.getElementById("sensitivityBtn");
const lapseModifiersInput = document.getElementById("lapseModifiers");
const stochasticBtn = document.getElementById("stochasticBtn");
const tailCards = document.getElementById("tailCards");

const vasicekFields = {
  r0: document.getElementById("vasicekR0"),
  kappa: document.getElementById("vasicekKappa"),
  theta: document.getElementById("vasicekTheta"),
  sigma: document.getElementById("vasicekSigma"),
  dt: document.getElementById("vasicekDt"),
  sims: document.getElementById("stochasticSims"),
  seed: document.getElementById("stochasticSeed"),
  maxPaths: document.getElementById("stochasticMaxPaths"),
};

const fields = {
  age: document.getElementById("age"),
  premium: document.getElementById("premium"),
  claims_amount: document.getElementById("claimsAmount"),
  policyholder_count: document.getElementById("policyholderCount"),
  projection_years: document.getElementById("projectionYears"),
  interest_rate: document.getElementById("interestRate"),
  inflation_rate: document.getElementById("inflationRate"),
  commission: document.getElementById("commission"),
  maintenance: document.getElementById("maintenance"),
  lapse_vector: document.getElementById("lapseVector"),
};

let products = {};
let cashflowChart = null;
let pvChart = null;
let sensitivityChart = null;
let ratePathsChart = null;
let funnelChart = null;
let npvHistChart = null;

function setStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.dataset.type = type;
}

function formatCurrency(value) {
  const num = Number(value) || 0;
  return num.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function formatPercent(value) {
  const num = Number(value) || 0;
  return `${(num * 100).toFixed(2)}%`;
}

function parseLapseVector(raw) {
  return raw
    .split(/[\n,]/)
    .map((value) => value.trim())
    .filter(Boolean)
    .map(Number)
    .filter((value) => !Number.isNaN(value));
}

function parseModifiers(raw) {
  if (!raw) return [];
  return raw
    .split(/[\n,]/)
    .map((value) => value.trim())
    .filter(Boolean)
    .map(Number)
    .filter((value) => !Number.isNaN(value));
}

function fillForm(productKey) {
  const product = products[productKey];
  if (!product) return;

  fields.age.value = product.age;
  fields.premium.value = product.premium;
  fields.claims_amount.value = product.claims_amount;
  fields.policyholder_count.value = product.policyholder_count;
  fields.projection_years.value = product.projection_years;
  fields.interest_rate.value = product.interest_rate;
  fields.inflation_rate.value = product.inflation_rate;
  fields.commission.value = product.expenses?.commission ?? 0;
  fields.maintenance.value = product.expenses?.maintenance ?? 0;
  fields.lapse_vector.value = product.lapse_vector?.join(", ") || "";
}

function buildPayload() {
  const lapseVector = parseLapseVector(fields.lapse_vector.value);

  return {
    product_key: productSelect.value,
    mortality_file: mortalityFileSelect.value,
    sheet_name: sheetNameInput.value || "Sheet1",
    inputs: {
      age: Number(fields.age.value),
      premium: Number(fields.premium.value),
      claims_amount: Number(fields.claims_amount.value),
      policyholder_count: Number(fields.policyholder_count.value),
      projection_years: Number(fields.projection_years.value),
      interest_rate: Number(fields.interest_rate.value),
      inflation_rate: Number(fields.inflation_rate.value),
      expenses: {
        commission: Number(fields.commission.value),
        maintenance: Number(fields.maintenance.value),
      },
      lapse_vector: lapseVector,
    },
  };
}

function buildAssumptions() {
  const lapseVector = parseLapseVector(fields.lapse_vector.value);
  return {
    age: Number(fields.age.value),
    premium: Number(fields.premium.value),
    claims_amount: Number(fields.claims_amount.value),
    policyholder_count: Number(fields.policyholder_count.value),
    projection_years: Number(fields.projection_years.value),
    interest_rate: Number(fields.interest_rate.value),
    inflation_rate: Number(fields.inflation_rate.value),
    expenses: {
      commission: Number(fields.commission.value),
      maintenance: Number(fields.maintenance.value),
    },
    lapse_vector: lapseVector,
  };
}

function renderSummary(metrics) {
  summaryCards.innerHTML = "";

  const items = [
    { label: "PV Premiums", value: formatCurrency(metrics.total_pv_premiums) },
    { label: "PV Claims", value: formatCurrency(metrics.total_pv_claims) },
    { label: "PV Expenses", value: formatCurrency(metrics.total_pv_expenses) },
    { label: "Net Cashflow", value: formatCurrency(metrics.total_net_cashflow) },
    { label: "NPV", value: formatCurrency(metrics.npv) },
    { label: "Profit Margin", value: formatPercent(metrics.profit_margin) },
  ];

  if (metrics.optimal_premium !== undefined && metrics.optimal_premium !== null) {
    items.unshift({ label: "Optimal Premium", value: formatCurrency(metrics.optimal_premium) });
  }

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "card";
    const title = document.createElement("h4");
    title.textContent = item.label;
    const value = document.createElement("p");
    value.textContent = item.value;
    card.append(title, value);
    summaryCards.appendChild(card);
  });
}

function renderCharts(projection) {
  const labels = projection.years;

  if (cashflowChart) cashflowChart.destroy();
  if (pvChart) pvChart.destroy();

  const cashCtx = document.getElementById("cashflowChart");
  cashflowChart = new Chart(cashCtx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Premiums", data: projection.premiums, borderColor: "#3b82f6" },
        { label: "Claims", data: projection.claims, borderColor: "#ef4444" },
        { label: "Expenses", data: projection.expenses, borderColor: "#f59e0b" },
        { label: "Net Cashflow", data: projection.net_cashflow, borderColor: "#111827", borderDash: [6, 4] },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { title: { display: true, text: "Policy Year" } },
        y: { title: { display: true, text: "Cashflow" } },
      },
    },
  });

  const pvCtx = document.getElementById("pvChart");
  pvChart = new Chart(pvCtx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "PV Cashflow", data: projection.pv_cashflow, borderColor: "#10b981" },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { title: { display: true, text: "Policy Year" } },
        y: { title: { display: true, text: "PV Cashflow" } },
      },
    },
  });
}

function renderTailCards(tailMetrics) {
  tailCards.innerHTML = "";

  const items = [
    { label: "Mean NPV", value: formatCurrency(tailMetrics.mean) },
    { label: "VaR 90%", value: formatCurrency(tailMetrics.var_90) },
    { label: "VaR 95%", value: formatCurrency(tailMetrics.var_95) },
    { label: "CTE 90%", value: formatCurrency(tailMetrics.cte_90) },
    { label: "CTE 95%", value: formatCurrency(tailMetrics.cte_95) },
  ];

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "card";
    const title = document.createElement("h4");
    title.textContent = item.label;
    const value = document.createElement("p");
    value.textContent = item.value;
    card.append(title, value);
    tailCards.appendChild(card);
  });
}

function renderSensitivityChart(results) {
  const labels = results.map((row) => row.modifier);
  const margins = results.map((row) => row.profit_margin * 100);
  const npvs = results.map((row) => row.npv);

  if (sensitivityChart) sensitivityChart.destroy();

  const ctx = document.getElementById("sensitivityChart");
  sensitivityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Profit Margin (%)",
          data: margins,
          borderColor: "#6366f1",
          yAxisID: "y",
        },
        {
          label: "NPV",
          data: npvs,
          borderColor: "#10b981",
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { title: { display: true, text: "Lapse Modifier" } },
        y: { title: { display: true, text: "Profit Margin (%)" } },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          title: { display: true, text: "NPV" },
        },
      },
    },
  });
}

function renderRatePathsChart(ratePaths) {
  if (!ratePaths || ratePaths.length === 0) return;

  if (ratePathsChart) ratePathsChart.destroy();

  const labels = ratePaths[0].map((_, idx) => idx);
  const datasets = ratePaths.map((path, idx) => ({
    label: `Path ${idx + 1}`,
    data: path,
    borderColor: "rgba(59, 130, 246, 0.08)",
    borderWidth: 1,
    pointRadius: 0,
  }));

  const ctx = document.getElementById("ratePathsChart");
  ratePathsChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: { title: { display: true, text: "Year" } },
        y: {
          title: { display: true, text: "Rate" },
          ticks: { callback: (value) => `${(value * 100).toFixed(1)}%` },
        },
      },
    },
  });
}

function renderFunnelChart(summary) {
  if (!summary) return;

  if (funnelChart) funnelChart.destroy();

  const labels = summary.years;
  const ctx = document.getElementById("funnelChart");
  funnelChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "P05",
          data: summary.p05,
          borderColor: "rgba(15, 23, 42, 0.35)",
          backgroundColor: "rgba(99, 102, 241, 0.15)",
          fill: "+1",
          pointRadius: 0,
        },
        {
          label: "P95",
          data: summary.p95,
          borderColor: "rgba(15, 23, 42, 0.35)",
          pointRadius: 0,
        },
        {
          label: "Mean",
          data: summary.mean,
          borderColor: "#ef4444",
          borderDash: [6, 4],
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { title: { display: true, text: "Year" } },
        y: {
          title: { display: true, text: "Rate" },
          ticks: { callback: (value) => `${(value * 100).toFixed(1)}%` },
        },
      },
    },
  });
}

function buildHistogram(values, bins = 30) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min) / bins || 1;
  const counts = new Array(bins).fill(0);
  const labels = new Array(bins).fill(0).map((_, i) => min + width * (i + 0.5));

  values.forEach((value) => {
    let idx = Math.floor((value - min) / width);
    if (idx >= bins) idx = bins - 1;
    if (idx < 0) idx = 0;
    counts[idx] += 1;
  });

  return { labels, counts };
}

function renderNpvHistogram(npvs) {
  if (!npvs || npvs.length === 0) return;

  if (npvHistChart) npvHistChart.destroy();

  const { labels, counts } = buildHistogram(npvs, 30);
  const ctx = document.getElementById("npvHistChart");
  npvHistChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels.map((value) => value.toFixed(0)),
      datasets: [
        {
          label: "NPV Count",
          data: counts,
          backgroundColor: "rgba(34, 197, 94, 0.45)",
          borderColor: "rgba(34, 197, 94, 0.8)",
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { title: { display: true, text: "NPV (binned)" } },
        y: { title: { display: true, text: "Count" } },
      },
    },
  });
}

async function loadProducts() {
  const res = await fetch("/api/products");
  const data = await res.json();
  products = data.products || {};

  productSelect.innerHTML = "";
  Object.keys(products).forEach((key) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = key;
    productSelect.appendChild(option);
  });

  const createOption = document.createElement("option");
  createOption.value = "__create__";
  createOption.textContent = "Create new";
  productSelect.appendChild(createOption);

  const defaultKey = products.product_A ? "product_A" : Object.keys(products)[0];
  if (defaultKey) {
    productSelect.value = defaultKey;
    fillForm(defaultKey);
  }
}

async function loadDataFiles() {
  const res = await fetch("/api/data-files");
  const data = await res.json();
  const files = data.files || [];

  mortalityFileSelect.innerHTML = "";
  files.forEach((file) => {
    const option = document.createElement("option");
    option.value = file;
    option.textContent = file;
    mortalityFileSelect.appendChild(option);
  });
}

async function uploadFile() {
  const file = fileUpload.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  setStatus("Uploading...", "loading");
  const res = await fetch("/api/upload", {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(data.error || "Upload failed", "error");
    return;
  }

  await loadDataFiles();
  mortalityFileSelect.value = data.uploaded;
  setStatus("Upload complete", "success");
}

async function runPricing() {
  if (productSelect.value === "__create__") {
    setStatus("Save the new product first", "error");
    return;
  }
  const payload = buildPayload();
  setStatus("Running...", "loading");

  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!res.ok) {
    setStatus(data.error || "Run failed", "error");
    return;
  }

  renderSummary(data.metrics);
  renderCharts(data.projection);
  setStatus("Complete", "success");
}

async function saveNewProduct() {
  const productKey = newProductNameInput.value.trim();
  if (!productKey) {
    setStatus("Enter a product name", "error");
    return;
  }

  const assumptions = buildAssumptions();
  setStatus("Saving product...", "loading");

  const res = await fetch("/api/products", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_key: productKey, assumptions }),
  });

  const data = await res.json();
  if (!res.ok) {
    setStatus(data.error || "Save failed", "error");
    return;
  }

  products = data.products || {};
  await loadProducts();
  productSelect.value = productKey;
  fillForm(productKey);
  newProductNameInput.value = "";
  toggleCreateMode(false);
  setStatus("Product saved", "success");
}

async function optimizeMargin() {
  if (productSelect.value === "__create__") {
    setStatus("Save the new product first", "error");
    return;
  }

  const payload = buildPayload();
  payload.target_margin = Number(targetMarginInput.value);

  if (Number.isNaN(payload.target_margin)) {
    setStatus("Enter a valid target margin", "error");
    return;
  }

  setStatus("Optimizing...", "loading");

  const res = await fetch("/api/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    setStatus(data.error || "Optimization failed", "error");
    return;
  }

  if (data.optimal_premium !== undefined) {
    fields.premium.value = Number(data.optimal_premium).toFixed(2);
  }

  renderSummary({
    ...data.metrics,
    optimal_premium: data.optimal_premium,
  });
  renderCharts(data.projection);
  setStatus("Optimization complete", "success");
}

async function runSensitivity() {
  if (productSelect.value === "__create__") {
    setStatus("Save the new product first", "error");
    return;
  }

  const payload = buildPayload();
  payload.lapse_modifiers = parseModifiers(lapseModifiersInput.value);

  setStatus("Running sensitivity...", "loading");
  const res = await fetch("/api/sensitivity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!res.ok) {
    setStatus(data.error || "Sensitivity failed", "error");
    return;
  }

  renderSensitivityChart(data.results || []);
  setStatus(data.cached ? "Sensitivity cached" : "Sensitivity complete", "success");
}

async function runStochastic() {
  if (productSelect.value === "__create__") {
    setStatus("Save the new product first", "error");
    return;
  }

  const payload = buildPayload();
  payload.n_simulations = Number(vasicekFields.sims.value) || 1000;
  payload.max_paths = Number(vasicekFields.maxPaths.value) || 200;

  if (vasicekFields.seed.value) {
    payload.seed = Number(vasicekFields.seed.value);
  }

  payload.vasicek = {
    r0: Number(vasicekFields.r0.value),
    kappa: Number(vasicekFields.kappa.value),
    theta: Number(vasicekFields.theta.value),
    sigma: Number(vasicekFields.sigma.value),
    dt: Number(vasicekFields.dt.value),
  };

  setStatus("Running stochastic...", "loading");

  const res = await fetch("/api/stochastic", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!res.ok) {
    setStatus(data.error || "Stochastic failed", "error");
    return;
  }

  const output = data.stochastic;
  renderTailCards(output.tail_metrics);
  renderRatePathsChart(output.rate_paths);
  renderFunnelChart(output.rate_path_summary);
  renderNpvHistogram(output.npvs);
  setStatus(data.cached ? "Stochastic cached" : "Stochastic complete", "success");
}

function toggleCreateMode(enabled) {
  if (enabled) {
    newProductRow.classList.remove("hidden");
    saveProductBtn.classList.remove("hidden");
  } else {
    newProductRow.classList.add("hidden");
    saveProductBtn.classList.add("hidden");
  }
}

productSelect.addEventListener("change", (event) => {
  if (event.target.value === "__create__") {
    toggleCreateMode(true);
  } else {
    toggleCreateMode(false);
    fillForm(event.target.value);
  }
});

uploadBtn.addEventListener("click", uploadFile);
runBtn.addEventListener("click", runPricing);
saveProductBtn.addEventListener("click", saveNewProduct);
optimizeBtn.addEventListener("click", optimizeMargin);
sensitivityBtn.addEventListener("click", runSensitivity);
stochasticBtn.addEventListener("click", runStochastic);

(async function init() {
  await loadProducts();
  await loadDataFiles();
})();
