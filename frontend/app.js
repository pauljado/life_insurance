const statusEl = document.getElementById("status");
const productSelect = document.getElementById("productSelect");
const mortalityFileSelect = document.getElementById("mortalityFile");
const sheetNameInput = document.getElementById("sheetName");
const uploadBtn = document.getElementById("uploadBtn");
const fileUpload = document.getElementById("fileUpload");
const runBtn = document.getElementById("runBtn");
const summaryCards = document.getElementById("summaryCards");

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

productSelect.addEventListener("change", (event) => {
  fillForm(event.target.value);
});

uploadBtn.addEventListener("click", uploadFile);
runBtn.addEventListener("click", runPricing);

(async function init() {
  await loadProducts();
  await loadDataFiles();
})();
