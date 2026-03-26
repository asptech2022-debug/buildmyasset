/**
 * BuildMyAsset — Frontend Script
 * Features: Dark/Light toggle · Multi-currency · Dynamic expenses
 * Stress meter · Dependency tracking · Worst month · Top expenses
 */

// ── State ──
let selectedAsset  = null;
let profileData    = {};
let houseStatus    = 'ready';
let planMode       = 'simple';
let expRowIdx      = 0;
let stageIdx       = 0;
let currency       = { code:'INR', symbol:'₹', name:'Indian Rupee' };

// ── Helpers ──
const $  = id => document.getElementById(id);
const v  = id => parseFloat($(id)?.value) || 0;
const iv = id => parseInt($(id)?.value)   || 0;
const sv = id => $(id)?.value?.trim()     || '';

function fmt(n) {
  n = Math.round(n);
  const sym = currency.symbol;
  // For INR use lakh/crore system
  if (currency.code === 'INR') {
    if (n >= 1e7) return sym + (n / 1e7).toFixed(2) + ' Cr';
    if (n >= 1e5) return sym + (n / 1e5).toFixed(2) + ' L';
    return sym + n.toLocaleString('en-IN');
  }
  // For others use K/M
  if (Math.abs(n) >= 1e6) return sym + (n / 1e6).toFixed(2) + 'M';
  if (Math.abs(n) >= 1e3) return sym + (n / 1e3).toFixed(1) + 'K';
  return sym + n.toLocaleString();
}
function fmtPct(n) { return (n || 0).toFixed(1) + '%'; }

// ══════════════════════════════════════════
//  THEME TOGGLE
// ══════════════════════════════════════════

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  localStorage.setItem('bma-theme', isDark ? 'light' : 'dark');
}

// Load saved theme on init
(function initTheme() {
  const saved = localStorage.getItem('bma-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
})();

// ══════════════════════════════════════════
//  CURRENCY SELECTION
// ══════════════════════════════════════════

const CURRENCIES = [
  { code:'INR', symbol:'₹',    name:'Indian Rupee',      flag:'🇮🇳' },
  { code:'USD', symbol:'$',    name:'US Dollar',          flag:'🇺🇸' },
  { code:'EUR', symbol:'€',    name:'Euro',               flag:'🇪🇺' },
  { code:'GBP', symbol:'£',    name:'British Pound',      flag:'🇬🇧' },
  { code:'AED', symbol:'د.إ', name:'UAE Dirham',          flag:'🇦🇪' },
  { code:'SGD', symbol:'S$',   name:'Singapore Dollar',   flag:'🇸🇬' },
  { code:'AUD', symbol:'A$',   name:'Australian Dollar',  flag:'🇦🇺' },
  { code:'CAD', symbol:'C$',   name:'Canadian Dollar',    flag:'🇨🇦' },
];

function toggleCurrencyDropdown() {
  const wrap = $('tbCurWrap');
  const dd   = $('curDropdown');
  if (!wrap || !dd) return;
  const isOpen = wrap.classList.contains('open');
  wrap.classList.toggle('open', !isOpen);
  dd.classList.toggle('open', !isOpen);
}

// Close dropdown when clicking outside
document.addEventListener('click', e => {
  const wrap = $('tbCurWrap');
  if (wrap && !wrap.contains(e.target)) {
    wrap.classList.remove('open');
    $('curDropdown')?.classList.remove('open');
  }
});

function pickCurrency(code, symbol, name, flag, el) {
  currency = { code, symbol, name, flag };

  // Update topbar button
  $('tbCurFlag').textContent = flag;
  $('tbCurText').textContent = symbol + ' ' + code;

  // Highlight active option in dropdown
  document.querySelectorAll('.cur-opt').forEach(o => o.classList.remove('active'));
  $('curopt-' + code)?.classList.add('active');

  // Highlight selected card on step 1 grid
  document.querySelectorAll('.cur-card').forEach(c => c.classList.remove('selected'));
  document.querySelectorAll(`.cur-card[onclick*="'${code}'"]`).forEach(c => c.classList.add('selected'));

  // Update all ₹ unit labels throughout the form
  document.querySelectorAll('.cur-unit').forEach(el => { el.textContent = symbol; });

  // Close the dropdown
  $('tbCurWrap')?.classList.remove('open');
  $('curDropdown')?.classList.remove('open');

  // Refresh live expense totals
  liveExpenses();
}

// Also hook step-1 grid cards to use the new pickCurrency signature
function pickCurrencyFromCard(code, el) {
  const cur = CURRENCIES.find(c => c.code === code);
  if (cur) pickCurrency(cur.code, cur.symbol, cur.name, cur.flag, el);
}

// ══════════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════════

function showApp()        { landToApp(null); }
function quickStart(type) { landToApp(type); }

function landToApp(type) {
  $('landingPage').style.display = 'none';
  $('appPage').style.display     = 'block';
  ensureOneExpRow();
  if (type) {
    pickAsset(type, document.querySelector(`[data-type="${type}"]`));
    showAssetForm(type);
    gotoStep(2);
  } else {
    gotoStep(1);
  }
  window.scrollTo({ top:0, behavior:'smooth' });
}

function goLanding() {
  $('appPage').style.display     = 'none';
  $('landingPage').style.display = '';
  resetAll();
  window.scrollTo({ top:0, behavior:'smooth' });
}

function resetAll() {
  selectedAsset = null; profileData = {};
  houseStatus = 'ready'; planMode = 'simple';
  expRowIdx = 0; stageIdx = 0;
  document.querySelectorAll('.asset-card').forEach(c => c.classList.remove('selected'));
  $('s1Next').disabled = true;
  $('profileEligBox').style.display = 'none';
  $('expenseRows').innerHTML = '';
  $('stageRows').innerHTML   = '';
  liveExpenses();
}

function gotoStep(n) {
  if (n === 3) showAssetForm(selectedAsset);
  for (let i = 1; i <= 4; i++) {
    const ws = $(`ws${i}`);
    if (ws) ws.style.display = (i === n) ? 'block' : 'none';
  }
  document.querySelectorAll('.tbs').forEach(el => {
    const s = parseInt(el.dataset.s);
    el.classList.remove('active','done');
    if (s === n) el.classList.add('active');
    if (s < n)   el.classList.add('done');
  });
  window.scrollTo({ top:0, behavior:'smooth' });
}

// ══════════════════════════════════════════
//  ASSET SELECTION
// ══════════════════════════════════════════

function pickAsset(type, el) {
  selectedAsset = type;
  document.querySelectorAll('.asset-card').forEach(c => c.classList.remove('selected'));
  document.querySelectorAll(`[data-type="${type}"]`).forEach(c => c.classList.add('selected'));
  $('s1Next').disabled = false;
}

function showAssetForm(type) {
  ['fHouse','fCar','fPlot'].forEach(id => $(id).style.display = 'none');
  const map  = { house:'fHouse', car:'fCar', plot:'fPlot' };
  const sub  = { house:'Enter property details for the full analysis.', car:'Enter vehicle details.', plot:'Enter plot/land details.' };
  const name = { house:'property', car:'vehicle', plot:'plot' };
  if (type && map[type]) {
    $(map[type]).style.display = 'block';
    $('assetNameInline').textContent = name[type] || type;
    $('assetSubline').textContent    = sub[type]  || '';
  }
}

// House status / plan mode
function setHStatus(val, btn) {
  houseStatus = val;
  document.querySelectorAll('#hStatusSeg .seg-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  $('payPlanBox').style.display = val === 'uc' ? 'block' : 'none';
}

function setPlanMode(val, btn) {
  planMode = val;
  document.querySelectorAll('#planModeSeg .seg-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  $('simplePlanNote').style.display = val === 'simple'   ? 'block' : 'none';
  $('advPlanWrap').style.display    = val === 'advanced' ? 'block' : 'none';
}

// Stages
function addStage() {
  stageIdx++;
  const id  = stageIdx;
  const row = document.createElement('div');
  row.className = 'stage-row'; row.id = `sr_${id}`;
  row.innerHTML = `
    <div class="field"><input type="text" id="sn_${id}" placeholder="Stage name…"/></div>
    <div class="field"><input type="number" id="sp_${id}" placeholder="%" min="0" max="100" step="0.5"/></div>
    <div class="field"><input type="number" id="sm_${id}" placeholder="Month" min="1"/></div>
    <button class="btn-rm-stage" onclick="document.getElementById('sr_${id}').remove()">×</button>
  `;
  $('stageRows').appendChild(row);
}

function collectStages() {
  const stages = [];
  document.querySelectorAll('[id^="sn_"]').forEach(el => {
    const id  = el.id.replace('sn_','');
    const pct = parseFloat($(`sp_${id}`)?.value) || 0;
    if (pct > 0) stages.push({ name:el.value||`Stage ${id}`, percentage:pct, month:parseInt($(`sm_${id}`)?.value)||0 });
  });
  return stages;
}

// ══════════════════════════════════════════
//  DYNAMIC EXPENSES
// ══════════════════════════════════════════

function ensureOneExpRow() {
  if ($('expenseRows').children.length === 0) addExpense();
}

function addExpense(name='', amount='', isDep=false) {
  expRowIdx++;
  const id  = expRowIdx;
  const row = document.createElement('div');
  row.className = 'exp-row'; row.id = `er_${id}`;
  row.innerHTML = `
    <input type="text" id="en_${id}" placeholder="e.g. Groceries, School Fees…" value="${name}" oninput="liveExpenses()"/>
    <input type="number" id="ea_${id}" placeholder="0" min="0" value="${amount}" oninput="liveExpenses()"/>
    <div class="dep-check">
      <input type="checkbox" id="ed_${id}" ${isDep?'checked':''} onchange="liveExpenses()"/>
      <span class="dep-pill">D</span>
    </div>
    <button class="btn-rm-exp" onclick="removeExpense(${id})">×</button>
  `;
  $('expenseRows').appendChild(row);
  liveExpenses();
}

function removeExpense(id) {
  if ($('expenseRows').children.length <= 1) { alert('At least one expense row required.'); return; }
  $(`er_${id}`)?.remove();
  liveExpenses();
}

function collectExpenses() {
  const rows = [];
  document.querySelectorAll('[id^="er_"]').forEach(row => {
    const id     = row.id.replace('er_','');
    const name   = $(`en_${id}`)?.value?.trim() || 'Expense';
    const amount = parseFloat($(`ea_${id}`)?.value) || 0;
    const isDep  = $(`ed_${id}`)?.checked || false;
    if (amount > 0) rows.push({ name, amount, dependency:isDep });
  });
  return rows;
}

function liveExpenses() {
  let total = 0, depTotal = 0;
  document.querySelectorAll('[id^="er_"]').forEach(row => {
    const id     = row.id.replace('er_','');
    const amount = parseFloat($(`ea_${id}`)?.value) || 0;
    const isDep  = $(`ed_${id}`)?.checked || false;
    total += amount;
    if (isDep) depTotal += amount;
  });
  const income   = v('p_income');
  const existing = v('p_existing');
  const free     = income - total - existing;

  $('expTotal').textContent    = fmt(total);
  $('expDepTotal').textContent = fmt(depTotal);
  $('expFreeCash').textContent = (free >= 0 ? '' : '−') + fmt(Math.abs(free));
  $('expFreeCash').style.color = free < 0 ? 'var(--rose)' : 'var(--accent)';
}

// ══════════════════════════════════════════
//  PROFILE CHECK
// ══════════════════════════════════════════

function validateProfile() {
  const income  = v('p_income');
  const savings = v('p_savings');
  const age     = iv('p_age');
  if (income   <= 0)        return pErr('Monthly income must be greater than zero.');
  if (savings   < 0)        return pErr('Savings cannot be negative.');
  if (age < 18 || age > 70) return pErr('Age must be between 18 and 70.');
  if (collectExpenses().length === 0) return pErr('Add at least one expense row with an amount.');
  return true;
}

function pErr(msg) {
  const box = $('profileEligBox');
  box.className = 'elig-box warn';
  box.innerHTML = '⚠️ ' + msg;
  box.style.display = 'block';
  return false;
}

async function runProfileCheck() {
  if (!validateProfile()) return;
  profileData = { monthly_income:v('p_income'), existing_emis:v('p_existing'), current_savings:v('p_savings'), age:iv('p_age') };
  const expenses = collectExpenses();
  try {
    const res  = await fetch('/check-profile', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...profileData, expenses}) });
    const data = await res.json();
    const box  = $('profileEligBox');
    box.style.display = 'block';
    if (data.eligible) {
      box.className = 'elig-box ok';
      box.innerHTML = `✅ <strong>Eligible.</strong> Free cash: <strong>${fmt(data.disposable)}/mo</strong> · Savings runway: <strong>${data.savings_months} months</strong> · Existing DTI: <strong>${fmtPct(data.dti_existing)}</strong>`;
    } else {
      box.className = 'elig-box warn';
      box.innerHTML = `⚠️ <strong>Caution:</strong> ${data.message} · DTI: <strong>${fmtPct(data.dti_existing)}</strong>`;
    }
    setTimeout(() => gotoStep(3), 900);
  } catch(e) { gotoStep(3); }
}

// ══════════════════════════════════════════
//  ASSET VALIDATION & COLLECTION
// ══════════════════════════════════════════

function validateAsset() {
  const err = $('assetErrBox');
  err.style.display = 'none';
  const e = msg => { err.textContent='⚠️ '+msg; err.style.display='block'; return false; };
  if (selectedAsset === 'house') {
    if (v('h_price') <= 0)  return e('Enter a valid property price.');
    if (v('h_down')  <= 0)  return e('Enter a down payment.');
    if (v('h_down') >= v('h_price')) return e('Down payment cannot exceed property price.');
    if (v('h_rate')  <= 0)  return e('Enter a valid interest rate.');
    if (iv('h_tenure') < 1) return e('Loan tenure must be at least 1 year.');
  }
  if (selectedAsset === 'car') {
    if (v('c_price') <= 0)  return e('Enter a valid car price.');
    if (v('c_down') >= v('c_price')) return e('Down payment cannot exceed car price.');
    if (v('c_rate')  <= 0)  return e('Enter a valid interest rate.');
    if (iv('c_tenure') < 1) return e('Loan tenure must be at least 1 year.');
  }
  if (selectedAsset === 'plot') {
    if (v('pl_price') <= 0) return e('Enter a valid plot price.');
    if (v('pl_down') > v('pl_price')) return e('Down payment cannot exceed plot price.');
  }
  return true;
}

function collectAsset() {
  if (selectedAsset === 'house') {
    const d = { property_price:v('h_price'), down_payment:v('h_down'), interest_rate:v('h_rate'), tenure_years:iv('h_tenure'), property_type:sv('h_type'), carpet_area:v('h_area'), status:houseStatus };
    if (houseStatus === 'uc' && planMode === 'advanced') d.stages = collectStages();
    return d;
  }
  if (selectedAsset === 'car')  return { car_type:sv('c_type'), car_price:v('c_price'), down_payment:v('c_down'), interest_rate:v('c_rate'), tenure_years:iv('c_tenure'), fuel_type:sv('c_fuel') };
  if (selectedAsset === 'plot') return { plot_price:v('pl_price'), plot_size:v('pl_size'), location_type:sv('pl_loc'), purpose:sv('pl_purpose'), down_payment:v('pl_down'), interest_rate:v('pl_rate'), tenure_years:iv('pl_tenure') };
}

// ══════════════════════════════════════════
//  ANALYZE
// ══════════════════════════════════════════

async function doAnalyze() {
  if (!validateAsset()) return;
  const btn = $('analyzeBtn');
  $('analyzeTxt').style.display  = 'none';
  $('analyzeLoad').style.display = 'inline';
  btn.disabled = true;
  try {
    const res  = await fetch('/analyze', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ asset_type:selectedAsset, profile:profileData, asset:collectAsset(), expenses:collectExpenses() }) });
    const data = await res.json();
    if (!res.ok) { showAssetErr(data.error || 'Server error.'); return; }
    renderResults(data);
    gotoStep(4);
  } catch(e) { showAssetErr('Could not connect to server.'); }
  finally {
    $('analyzeTxt').style.display  = 'inline';
    $('analyzeLoad').style.display = 'none';
    btn.disabled = false;
  }
}

function showAssetErr(msg) { $('assetErrBox').textContent='⚠️ '+msg; $('assetErrBox').style.display='block'; }

// ══════════════════════════════════════════
//  RENDER RESULTS
// ══════════════════════════════════════════

function renderResults(data) {
  const { decision, confidence, summary, flags, timeline, worst_month,
          stress_meter, top3_expenses, dep_names, dep_total,
          rent_vs_buy, metrics, alternative, asset_type } = data;

  const cls  = { SAFE:'safe', RISKY:'risky', NOT_RECOMMENDED:'danger' };
  const icon = { SAFE:'✅', RISKY:'⚠️', NOT_RECOMMENDED:'❌' };
  const lbl  = { SAFE:'Safe to Buy', RISKY:'Risky Decision', NOT_RECOMMENDED:'Not Recommended' };
  const atag = { house:'🏠 House Analysis', car:'🚗 Car Analysis', plot:'🌆 Plot Analysis' };

  // Hero
  const hero = $('resHero');
  hero.className = `res-hero ${cls[decision]}`;
  $('rhTag').textContent     = atag[asset_type] || '';
  $('rhCur').textContent     = currency.symbol + ' ' + currency.code;
  $('rhConf').textContent    = `Confidence: ${confidence}`;
  $('rhIcon').textContent    = icon[decision];
  $('rhLabel').textContent   = lbl[decision];
  $('rhSummary').textContent = summary;

  // Stress meter
  const sm = stress_meter;
  const sc = $('stressCard');
  sc.className = `stress-card ${sm.level.toLowerCase()}`;
  $('scScore').textContent = sm.score;
  $('scLevel').textContent = sm.level + ' RISK';
  $('scDesc').textContent  = stressDesc(sm.score, sm.level);
  setTimeout(() => { $('scBarFill').style.width = sm.score + '%'; }, 100);

  // Metrics
  buildMetrics(metrics, asset_type);

  // Top expenses
  const topList = $('topExpList');
  topList.innerHTML = (top3_expenses?.length > 0)
    ? top3_expenses.map(ex => `<div class="ic-row"><span>${ex.name}${ex.dependency?` <span class="dep-tag">DEP</span>`:''}</span><span>${fmt(ex.amount)}</span></div>`).join('')
    : '<div style="font-size:13px;color:var(--ink40)">No expense data</div>';

  // Dependencies
  const depList = $('depList');
  depList.innerHTML = dep_names?.length > 0
    ? dep_names.map(n => `<div class="ic-row"><span>🔗 ${n}</span><span class="dep-tag">Essential</span></div>`).join('') + (dep_total > 0 ? `<div class="ic-row" style="margin-top:8px;border-top:1px solid var(--ink08);padding-top:8px"><span>Total</span><span>${fmt(dep_total)}/mo</span></div>` : '')
    : '<div style="font-size:13px;color:var(--ink40)">No dependencies flagged</div>';

  // DTI mini
  const dtiF = $('dtiMiniFill');
  if (metrics.dti_ratio > 0) {
    const dc = metrics.dti_ratio > 50 ? 'danger' : metrics.dti_ratio > 35 ? 'risky' : 'safe';
    dtiF.className = `dti-fill ${dc}`;
    $('dtiMiniVal').textContent = fmtPct(metrics.dti_ratio);
    setTimeout(() => { dtiF.style.width = Math.min(metrics.dti_ratio, 100) + '%'; }, 150);
  } else { $('dtiMiniVal').textContent = 'N/A'; }

  // Smart alternative
  if (alternative?.show) {
    $('altBanner').style.display = 'flex';
    const at = {house:'property',car:'car',plot:'plot'}[asset_type]||'asset';
    $('abBody').innerHTML = `Based on your income and expenses, you can safely afford a ${at} priced up to <strong>${fmt(alternative.max_price)}</strong> (EMI ≈ <strong>${fmt(alternative.max_emi)}/mo</strong>, keeping DTI under 38%).`;
  } else { $('altBanner').style.display = 'none'; }

  // Worst month
  if (worst_month) {
    $('worstAlert').style.display = 'flex';
    $('waBody').innerHTML = `<strong>Stage "${worst_month.name}"</strong> in Month ${worst_month.month} requires <strong>${fmt(worst_month.amount)}</strong> — may exceed your projected savings at that point. Plan ahead or negotiate a deferred schedule.`;
  } else { $('worstAlert').style.display = 'none'; }

  // Rent vs Buy
  if (rent_vs_buy) {
    $('rvbCard').style.display = 'block';
    const rvb = rent_vs_buy; const buyWins = !rvb.rent_cheaper;
    $('rvbCols').innerHTML = `
      <div class="rvb-col ${rvb.rent_cheaper?'winner':''}">
        ${rvb.rent_cheaper?'<div class="rvb-win">Lower cost</div>':''}
        <div class="rvb-col-lbl">Rent — 10 Years</div>
        <div class="rvb-val">${fmt(rvb.rent_10yr)}</div>
        <div class="rvb-sub">${fmt(rvb.monthly_rent)}/month</div>
      </div>
      <div class="rvb-col ${buyWins?'winner':''}">
        ${buyWins?'<div class="rvb-win">Builds equity</div>':''}
        <div class="rvb-col-lbl">Buy — Net Cost 10 Yrs</div>
        <div class="rvb-val">${fmt(Math.max(rvb.buy_cost_10yr,0))}</div>
        <div class="rvb-sub">Property value in 10yr: ${fmt(rvb.value_10yr)}</div>
      </div>`;
    $('rvbNote').textContent = rvb.recommendation;
  } else { $('rvbCard').style.display = 'none'; }

  // Timeline
  if (timeline?.length > 0) {
    $('tlCard').style.display = 'block';
    $('tlBody').innerHTML = timeline.map(t => `
      <tr>
        <td><strong>${t.name}</strong></td><td>Month ${t.month}</td><td>${t.pct}%</td>
        <td><strong>${fmt(t.amount)}</strong></td><td>${fmt(t.savings)}</td>
        <td>${t.stress?`<span style="color:var(--rose);font-weight:700">−${fmt(t.shortfall)}</span>`:'<span style="color:var(--accent)">OK</span>'}</td>
        <td><span class="${t.stress?'tl-stress':'tl-ok'}">${t.stress?'⚠️ Watch':'✅ Funded'}</span></td>
      </tr>`).join('');
  } else { $('tlCard').style.display = 'none'; }

  // Plot appreciation
  if (asset_type === 'plot' && metrics.value_5yr) {
    $('apprCard').style.display = 'block';
    $('apprCols').innerHTML = `
      <div class="appr-col"><div class="appr-lbl">Today</div><div class="appr-val">${fmt(v('pl_price')||0)}</div></div>
      <div class="appr-col"><div class="appr-lbl">5-Year Value</div><div class="appr-val">${fmt(metrics.value_5yr)}</div></div>
      <div class="appr-col hi"><div class="appr-lbl">10-Year (~${metrics.appr_pct}%/yr)</div><div class="appr-val">${fmt(metrics.value_10yr)}</div></div>`;
  } else { $('apprCard').style.display = 'none'; }

  // Flags
  const wrap = $('flagsWrap');
  wrap.innerHTML = '';
  (flags||[]).forEach((f,i) => {
    const row = document.createElement('div');
    row.className = `flag-row ${f.level}`;
    row.style.animationDelay = `${i*0.06}s`;
    row.innerHTML = `<span class="flag-emoji">${f.icon}</span><span>${f.msg}</span>`;
    wrap.appendChild(row);
  });
}

// ── Build metric cards ──
function buildMetrics(m, at) {
  const row = $('metricsRow'); row.innerHTML = '';
  const cards = [];
  if (m.monthly_emi > 0)         cards.push({icon:'📅', val:fmt(m.monthly_emi),    lbl:'Monthly EMI'});
  if (m.total_interest > 0)      cards.push({icon:'💸', val:fmt(m.total_interest), lbl:'Total Interest'});
  if (m.loan_end_age)            cards.push({icon:'🎂', val:m.loan_end_age+' yrs', lbl:'Loan End Age'});
  if (m.actual_cost)             cards.push({icon:'🏷️', val:fmt(m.actual_cost),    lbl:'Actual Cost', sub:'incl. taxes/reg.'});
  if (m.free_cash !== undefined) { const fc=m.free_cash; cards.push({icon:fc>=0?'💰':'🔴', val:fmt(Math.abs(fc)), lbl:fc>=0?'Monthly Free Cash':'Monthly Shortfall'}); }
  if (m.savings_after !== undefined) cards.push({icon:'🛡️', val:fmt(m.savings_after), lbl:'Savings After DP'});
  if (at==='car' && m.resale_5yr)    cards.push({icon:'📉', val:fmt(m.resale_5yr),     lbl:'5-yr Resale Value', sub:'~40% of price'});
  if (at==='car' && m.running_monthly) cards.push({icon:'⛽', val:fmt(m.running_monthly), lbl:'Running Cost/Mo'});
  if (m.dti_stress_20pct)        cards.push({icon:'⚡', val:fmtPct(m.dti_stress_20pct), lbl:'DTI @ −20% Income', sub:'Stress test'});
  cards.forEach(c => {
    row.innerHTML += `<div class="mc"><div class="mc-icon">${c.icon}</div><div class="mc-val">${c.val}</div><div class="mc-lbl">${c.lbl}</div>${c.sub?`<div class="mc-sub">${c.sub}</div>`:''}</div>`;
  });
}

// ── Stress level description ──
function stressDesc(score, level) {
  if (level==='LOW')    return `Score ${score}/100. Financial obligations are well within your income. This purchase appears sustainable.`;
  if (level==='MEDIUM') return `Score ${score}/100. Moderate strain detected. Feasible but leaves limited room for surprises.`;
  return `Score ${score}/100. High stress across multiple dimensions. This purchase could seriously strain your finances.`;
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
  ensureOneExpRow();
  // Animate landing preview bar
  setTimeout(() => {
    const fill = document.querySelector('.pc-bar-fill');
    if (fill) fill.style.width = '28%';
  }, 600);
  // Clear errors on input
  document.querySelectorAll('input').forEach(el => {
    el.addEventListener('input', () => { $('assetErrBox')?.setAttribute('style','display:none'); });
  });
});
