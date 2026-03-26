"""
AssetIQ v3 — Should I Buy This Asset?
Flask Backend — Complete Financial Decision Engine

New in V3:
  - Dynamic expense system with dependency flags
  - Financial Stress Meter (0-100 score)
  - Monthly Free Cash calculation
  - Top 3 expense detection
  - Worst month detection (staged payments)
  - Dependency expense display in results
"""

from flask import Flask, render_template, request, jsonify
import math
import os

app = Flask(__name__)


# ══════════════════════════════════════════════════
#  CORE UTILITIES
# ══════════════════════════════════════════════════

def calc_emi(principal, annual_rate, tenure_years):
    """Standard EMI formula: P*r*(1+r)^n / ((1+r)^n-1)"""
    if annual_rate <= 0 or principal <= 0:
        months = max(tenure_years * 12, 1)
        return round(principal / months, 2)
    r = annual_rate / (12 * 100)
    n = tenure_years * 12
    return round(principal * r * (1 + r)**n / ((1 + r)**n - 1), 2)


def dti_level(ratio):
    if ratio > 50: return "NOT_RECOMMENDED"
    if ratio > 35: return "RISKY"
    return "SAFE"


def combine(*levels):
    if "NOT_RECOMMENDED" in levels: return "NOT_RECOMMENDED"
    if "RISKY"           in levels: return "RISKY"
    return "SAFE"


def flag(level, icon, msg):
    return {"level": level, "icon": icon, "msg": msg}


# ══════════════════════════════════════════════════
#  EXPENSE PROCESSING
# ══════════════════════════════════════════════════

def process_expenses(expense_list):
    """
    Process dynamic expense rows.
    Returns total, dependency total, top 3, and dependency names.
    """
    total         = 0.0
    dep_total     = 0.0
    dep_names     = []
    items         = []

    for row in expense_list:
        name   = row.get("name", "Expense").strip() or "Expense"
        amount = float(row.get("amount", 0))
        is_dep = bool(row.get("dependency", False))
        if amount <= 0:
            continue
        total += amount
        items.append({"name": name, "amount": amount, "dependency": is_dep})
        if is_dep:
            dep_total += amount
            dep_names.append(name)

    # Top 3 by amount
    top3 = sorted(items, key=lambda x: x["amount"], reverse=True)[:3]
    return {
        "total":      round(total, 2),
        "dep_total":  round(dep_total, 2),
        "dep_names":  dep_names,
        "top3":       top3,
        "items":      items,
    }


# ══════════════════════════════════════════════════
#  FINANCIAL STRESS METER
# ══════════════════════════════════════════════════

def stress_meter(income, total_expenses, new_emi, existing_emis, savings, savings_after_dp, ef_needed):
    """
    Compute a 0-100 stress score.
    Higher = more financial stress.
    Factors: DTI, emergency fund gap, disposable income ratio, savings buffer.
    """
    score = 0

    # 1. DTI contribution (max 40 pts)
    total_emi = new_emi + existing_emis
    dti = (total_emi / income * 100) if income > 0 else 100
    if   dti > 70: score += 40
    elif dti > 50: score += 32
    elif dti > 35: score += 20
    elif dti > 20: score += 10
    else:          score += 0

    # 2. Emergency fund (max 25 pts)
    if   savings_after_dp < 0:          score += 25
    elif savings_after_dp < ef_needed:
        gap_ratio = 1 - (savings_after_dp / ef_needed)
        score += round(gap_ratio * 20)
    # else 0

    # 3. Disposable income (max 25 pts)
    disposable = income - total_expenses - total_emi
    disp_ratio = disposable / income if income > 0 else -1
    if   disp_ratio < 0:    score += 25
    elif disp_ratio < 0.05: score += 18
    elif disp_ratio < 0.10: score += 10
    elif disp_ratio < 0.20: score += 4
    # else 0

    # 4. Savings buffer vs cost (max 10 pts)
    if savings < total_expenses * 3:    score += 10
    elif savings < total_expenses * 6:  score += 5

    score = min(score, 100)

    if   score >= 65: level = "HIGH"
    elif score >= 35: level = "MEDIUM"
    else:             level = "LOW"

    return {"score": score, "level": level}


# ══════════════════════════════════════════════════
#  PROFILE CHECK (Step 2)
# ══════════════════════════════════════════════════

@app.route("/check-profile", methods=["POST"])
def check_profile():
    try:
        d        = request.get_json()
        income   = float(d["monthly_income"])
        existing = float(d.get("existing_emis", 0))
        savings  = float(d["current_savings"])
        age      = int(d.get("age", 30))
        exp_data = process_expenses(d.get("expenses", []))

        total_exp   = exp_data["total"]
        disposable  = income - total_exp - existing
        dti_existing= (existing / income * 100) if income > 0 else 0
        sav_months  = savings / total_exp if total_exp > 0 else 9999
        eligible    = disposable > 0 and dti_existing <= 60

        return jsonify({
            "eligible":       eligible,
            "disposable":     round(disposable, 2),
            "total_expenses": round(total_exp, 2),
            "dti_existing":   round(dti_existing, 1),
            "savings_months": round(sav_months, 1),
            "dep_names":      exp_data["dep_names"],
            "top3":           exp_data["top3"],
            "message": ("Baseline finances look healthy — proceed to asset details."
                        if eligible else
                        "High existing obligations. Additional purchase may strain your finances.")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ══════════════════════════════════════════════════
#  HOUSE ANALYSIS
# ══════════════════════════════════════════════════

def analyze_house(p, a, exp_data):
    income    = float(p["monthly_income"])
    existing  = float(p.get("existing_emis", 0))
    savings   = float(p["current_savings"])
    age       = int(p.get("age", 30))
    expenses  = exp_data["total"]
    dep_total = exp_data["dep_total"]

    price    = float(a["property_price"])
    down     = float(a["down_payment"])
    rate     = float(a["interest_rate"])
    tenure   = int(a["tenure_years"])
    status   = a.get("status", "ready")

    # Hidden costs (11% stamp duty + registration)
    hidden_pct   = 0.11
    hidden_costs = round(price * hidden_pct, 2)
    actual_cost  = price + hidden_costs

    loan           = price - down
    monthly_emi    = calc_emi(loan, rate, tenure)
    total_payment  = monthly_emi * tenure * 12
    total_interest = total_payment - loan
    loan_end_age   = age + tenure
    savings_after  = savings - down
    ef_needed      = expenses * 6
    total_emi_b    = monthly_emi + existing
    dti            = (total_emi_b / income * 100) if income > 0 else 0
    free_cash      = income - expenses - total_emi_b

    flags = []

    # Hidden costs
    flags.append(flag("warning","🧾",
        f"Actual cost includes ≈11% hidden costs (registration, stamp duty). "
        f"True price: ₹{actual_cost:,.0f} (+₹{hidden_costs:,.0f})."))

    # DTI
    if dti > 50:
        flags.append(flag("danger","📊",f"EMI consumes {dti:.1f}% of income — exceeds safe 50% limit."))
    elif dti > 35:
        flags.append(flag("warning","📊",f"EMI is {dti:.1f}% of income — above comfortable 35%."))
    else:
        flags.append(flag("success","📊",f"EMI is {dti:.1f}% of income — healthy range."))

    # Down payment
    dp_pct = (down / price * 100)
    if dp_pct < 10:
        flags.append(flag("danger","🏦",f"Down payment {dp_pct:.1f}% is very low — high loan burden."))
    elif dp_pct < 20:
        flags.append(flag("warning","🏦",f"Down payment {dp_pct:.1f}% — below recommended 20%."))
    else:
        flags.append(flag("success","🏦",f"Down payment {dp_pct:.1f}% — excellent leverage position."))

    # Emergency fund
    if savings_after < 0:
        flags.append(flag("danger","🛡️","Savings insufficient to cover down payment."))
    elif savings_after < ef_needed:
        flags.append(flag("warning","🛡️",
            f"Post-DP savings ₹{savings_after:,.0f} — below 6-month fund of ₹{ef_needed:,.0f}."))
    else:
        flags.append(flag("success","🛡️",
            f"₹{savings_after:,.0f} remains — 6-month emergency fund intact."))

    # Dependency expenses
    if dep_total > 0 and dep_total > income * 0.20:
        flags.append(flag("warning","👨‍👩‍👧",
            f"Dependency expenses total ₹{dep_total:,.0f}/mo — {dep_total/income*100:.1f}% of income. "
            f"These cannot be reduced easily: {', '.join(exp_data['dep_names'])}."))
    elif dep_total > 0:
        flags.append(flag("success","👨‍👩‍👧",
            f"Dependency expenses (₹{dep_total:,.0f}/mo) are manageable within your income."))

    # Free cash
    if free_cash < 0:
        flags.append(flag("danger","💸",f"Monthly shortfall ₹{abs(free_cash):,.0f} — income cannot cover all obligations."))
    elif free_cash < income * 0.10:
        flags.append(flag("warning","💸",f"Only ₹{free_cash:,.0f}/mo free after all obligations — very thin margin."))
    else:
        flags.append(flag("success","💸",f"₹{free_cash:,.0f}/mo free cash — healthy buffer."))

    # Risk simulation (20% income drop)
    income_80   = income * 0.80
    dti_stress  = (total_emi_b / income_80 * 100)
    flags.append(flag(
        "success" if dti_stress <= 50 else "warning","⚡",
        f"Stress test: 20% income drop → EMI burden {dti_stress:.1f}% "
        f"({'manageable ✓' if dti_stress <= 50 else 'exceeds limit ⚠️'})."))

    # Rent vs Buy
    monthly_rent     = price * 0.035 / 12
    rent_10yr        = monthly_rent * 120
    appr_rate        = 0.06
    value_10yr       = price * (1 + appr_rate) ** 10
    equity_gain      = value_10yr - price
    buy_cost_10yr    = (total_payment * min(10/tenure,1)) + down + hidden_costs - equity_gain
    rent_cheaper     = rent_10yr < buy_cost_10yr

    # Cash flow timeline for under-construction
    timeline      = []
    worst_month   = None
    worst_amount  = 0

    if status == "under_construction" and a.get("stages"):
        pre_emi_disp = income - expenses - existing
        run_savings  = savings - down
        for i, stage in enumerate(a["stages"]):
            stage_amt = price * float(stage.get("percentage",0)) / 100
            month_no  = int(stage.get("month",0))
            projected = run_savings + pre_emi_disp * 0.5 * month_no
            stress    = projected < stage_amt

            timeline.append({
                "name":     stage.get("name", f"Stage {i+1}"),
                "month":    month_no,
                "pct":      float(stage.get("percentage",0)),
                "amount":   round(stage_amt, 2),
                "savings":  round(projected, 2),
                "stress":   stress,
                "shortfall":round(max(stage_amt - projected, 0), 2),
            })

            if stress and stage_amt > worst_amount:
                worst_amount = stage_amt
                worst_month  = {"name": stage.get("name"), "month": month_no, "amount": round(stage_amt,2)}

    # Smart alternative
    max_emi_aff  = (income * 0.38) - existing
    max_loan_aff = 0
    if max_emi_aff > 0 and rate > 0:
        r = rate / (12*100); n = tenure*12
        max_loan_aff = max_emi_aff * ((1+r)**n - 1) / (r*(1+r)**n)
    max_price_aff = max(max_loan_aff + down, 0)

    # Stress meter
    sm = stress_meter(income, expenses, monthly_emi, existing, savings, savings_after, ef_needed)

    # Decision
    verdicts = [dti_level(dti)]
    if savings_after < 0:           verdicts.append("NOT_RECOMMENDED")
    elif savings_after < ef_needed: verdicts.append("RISKY")
    if free_cash < 0:               verdicts.append("NOT_RECOMMENDED")
    elif free_cash < income*0.10:   verdicts.append("RISKY")

    decision   = combine(*verdicts)
    confidence = "High" if verdicts.count("NOT_RECOMMENDED") + verdicts.count("RISKY") >= 2 else "Medium"

    summaries = {
        "SAFE":           "Your financial profile comfortably supports this purchase. EMI is manageable, savings are intact, and you retain a healthy monthly buffer.",
        "RISKY":          "Purchase is possible but financially tight. Any income disruption or emergency could cause stress. Proceed with caution.",
        "NOT_RECOMMENDED":"Multiple critical risk factors detected. This purchase could destabilise your finances. Consider a lower price point or building more savings first."
    }

    return {
        "decision":     decision, "confidence": confidence, "summary": summaries[decision],
        "flags":        flags,
        "timeline":     timeline,
        "worst_month":  worst_month,
        "stress_meter": sm,
        "top3_expenses":exp_data["top3"],
        "dep_names":    exp_data["dep_names"],
        "dep_total":    exp_data["dep_total"],
        "rent_vs_buy": {
            "monthly_rent":     round(monthly_rent, 2),
            "rent_10yr":        round(rent_10yr, 2),
            "buy_cost_10yr":    round(max(buy_cost_10yr, 0), 2),
            "equity_gain":      round(equity_gain, 2),
            "value_10yr":       round(value_10yr, 2),
            "rent_cheaper":     rent_cheaper,
            "recommendation":   (
                f"Renting at ₹{monthly_rent:,.0f}/mo totals ₹{rent_10yr:,.0f} over 10 years. "
                + (f"Buying, after loan costs and appreciation, nets ≈₹{max(buy_cost_10yr,0):,.0f}. "
                   f"{'Renting is cheaper in this scenario.' if rent_cheaper else 'Buying builds equity of ₹'+f'{equity_gain:,.0f} — stronger long-term.'}")
            )
        },
        "metrics": {
            "loan_amount":      round(loan, 2),
            "monthly_emi":      round(monthly_emi, 2),
            "total_interest":   round(total_interest, 2),
            "total_payment":    round(total_payment, 2),
            "actual_cost":      round(actual_cost, 2),
            "hidden_costs":     round(hidden_costs, 2),
            "dp_percent":       round(dp_pct, 1),
            "dti_ratio":        round(dti, 1),
            "loan_end_age":     loan_end_age,
            "savings_after":    round(savings_after, 2),
            "free_cash":        round(free_cash, 2),
            "dti_stress_20pct": round(dti_stress, 1),
        },
        "alternative": {
            "show":      decision != "SAFE" and 0 < max_price_aff < price,
            "max_price": round(max_price_aff, 2),
            "max_emi":   round(max(max_emi_aff, 0), 2),
        }
    }


# ══════════════════════════════════════════════════
#  CAR ANALYSIS
# ══════════════════════════════════════════════════

def analyze_car(p, a, exp_data):
    income   = float(p["monthly_income"])
    existing = float(p.get("existing_emis", 0))
    savings  = float(p["current_savings"])
    age      = int(p.get("age", 30))
    expenses = exp_data["total"]
    dep_total= exp_data["dep_total"]

    price    = float(a["car_price"])
    down     = float(a["down_payment"])
    rate     = float(a["interest_rate"])
    tenure   = int(a["tenure_years"])
    fuel     = a.get("fuel_type","Petrol")

    loan           = price - down
    monthly_emi    = calc_emi(loan, rate, tenure)
    total_payment  = monthly_emi * tenure * 12
    total_interest = total_payment - loan
    loan_end_age   = age + tenure
    savings_after  = savings - down
    ef_needed      = expenses * 6
    total_emi_b    = monthly_emi + existing
    dti            = (total_emi_b / income * 100) if income > 0 else 0

    # Running costs
    fuel_map     = {"Petrol":7000,"Diesel":5500,"Electric":2000,"CNG":3500}
    running_mo   = fuel_map.get(fuel, 6000) + 2000
    free_cash    = income - expenses - total_emi_b - running_mo

    # Depreciation
    resale_5yr   = max(price * 0.40, 0)   # 60% lost in 5 yrs
    net_loss_5yr = (total_payment + down) - resale_5yr

    flags = []

    flags.append(flag("warning","📉",
        f"Cars depreciate ~60% in 5 years. Estimated resale: ₹{resale_5yr:,.0f}. "
        f"Net financial loss (including loan): ₹{max(net_loss_5yr,0):,.0f}."))

    fuel_costs_note = f"Estimated running costs ({fuel}): ₹{running_mo:,.0f}/mo (fuel + maintenance + insurance)."
    flags.append(flag("warning","⛽", fuel_costs_note))

    if dti > 50:
        flags.append(flag("danger","📊",f"EMI burden {dti:.1f}% — exceeds safe limit."))
    elif dti > 35:
        flags.append(flag("warning","📊",f"EMI burden {dti:.1f}% — above 35% threshold."))
    else:
        flags.append(flag("success","📊",f"EMI burden {dti:.1f}% — within healthy range."))

    if savings_after < ef_needed:
        flags.append(flag("warning" if savings_after >= 0 else "danger","🛡️",
            f"Post-DP savings ₹{savings_after:,.0f} vs 6-month fund needed ₹{ef_needed:,.0f}."))
    else:
        flags.append(flag("success","🛡️",f"Emergency fund intact: ₹{savings_after:,.0f} available."))

    if dep_total > 0:
        flags.append(flag("warning" if dep_total > income*0.15 else "success","👨‍👩‍👧",
            f"Dependency expenses: ₹{dep_total:,.0f}/mo ({', '.join(exp_data['dep_names'])})."))

    if free_cash < 0:
        flags.append(flag("danger","💸",f"Monthly shortfall ₹{abs(free_cash):,.0f} including running costs."))
    elif free_cash < income*0.08:
        flags.append(flag("warning","💸",f"Only ₹{free_cash:,.0f}/mo after all costs — very tight."))
    else:
        flags.append(flag("success","💸",f"₹{free_cash:,.0f}/mo free cash after all expenses."))

    income_80  = income * 0.80
    dti_stress = (total_emi_b / income_80 * 100)
    flags.append(flag("success" if dti_stress<=50 else "warning","⚡",
        f"Stress test (20% income drop): EMI burden becomes {dti_stress:.1f}% "
        f"({'OK ✓' if dti_stress<=50 else 'tight ⚠️'})."))

    sm = stress_meter(income, expenses, monthly_emi, existing, savings, savings_after, ef_needed)

    max_emi_aff  = (income * 0.30) - existing
    max_loan_aff = 0
    if max_emi_aff > 0 and rate > 0:
        r = rate/(12*100); n = tenure*12
        max_loan_aff = max_emi_aff * ((1+r)**n - 1) / (r*(1+r)**n)
    max_price_aff = max(max_loan_aff + down, 0)

    verdicts = [dti_level(dti)]
    if savings_after < ef_needed: verdicts.append("RISKY")
    if free_cash < 0:             verdicts.append("NOT_RECOMMENDED")

    decision = combine(*verdicts)
    summaries = {
        "SAFE":           "Your finances can support this vehicle purchase. Factor in running costs and depreciation in your long-term planning.",
        "RISKY":          "Feasible but tight. Cars lose value while your loan obligation remains. Consider a lower price or larger down payment.",
        "NOT_RECOMMENDED":"This car purchase would strain your finances significantly. Explore lower-cost options or improve savings first."
    }

    return {
        "decision":      decision, "confidence":"High", "summary":summaries[decision],
        "flags":         flags, "timeline":[], "worst_month":None,
        "stress_meter":  sm,
        "top3_expenses": exp_data["top3"],
        "dep_names":     exp_data["dep_names"],
        "dep_total":     exp_data["dep_total"],
        "rent_vs_buy":   None,
        "metrics": {
            "loan_amount":      round(loan,2),
            "monthly_emi":      round(monthly_emi,2),
            "total_interest":   round(total_interest,2),
            "total_payment":    round(total_payment+down,2),
            "dti_ratio":        round(dti,1),
            "loan_end_age":     loan_end_age,
            "savings_after":    round(savings_after,2),
            "free_cash":        round(free_cash,2),
            "resale_5yr":       round(resale_5yr,2),
            "running_monthly":  round(running_mo,2),
            "dti_stress_20pct": round(dti_stress,1),
        },
        "alternative": {
            "show":      decision!="SAFE" and 0 < max_price_aff < price,
            "max_price": round(max_price_aff,2), "max_emi":round(max(max_emi_aff,0),2),
        }
    }


# ══════════════════════════════════════════════════
#  PLOT ANALYSIS
# ══════════════════════════════════════════════════

def analyze_plot(p, a, exp_data):
    income   = float(p["monthly_income"])
    existing = float(p.get("existing_emis", 0))
    savings  = float(p["current_savings"])
    age      = int(p.get("age", 30))
    expenses = exp_data["total"]
    dep_total= exp_data["dep_total"]

    price     = float(a["plot_price"])
    down      = float(a.get("down_payment", price))
    rate      = float(a.get("interest_rate", 0))
    tenure    = int(a.get("tenure_years", 0))
    purpose   = a.get("purpose","investment")
    loc_type  = a.get("location_type","suburban")

    hidden_costs = round(price * 0.07, 2)
    actual_cost  = price + hidden_costs
    has_loan     = (down < price) and (tenure > 0) and (rate > 0)
    loan         = price - down
    monthly_emi  = calc_emi(loan, rate, tenure) if has_loan else 0
    total_payment= monthly_emi*tenure*12 if has_loan else price
    savings_after= savings - down
    ef_needed    = expenses * 6

    appr_map     = {"urban":0.08,"suburban":0.06,"rural":0.04,"highway":0.07}
    appr_rate    = appr_map.get(loc_type, 0.05)
    value_5yr    = round(price * (1+appr_rate)**5, 2)
    value_10yr   = round(price * (1+appr_rate)**10, 2)

    total_emi_b = monthly_emi + existing
    dti         = (total_emi_b / income * 100) if (income > 0 and monthly_emi > 0) else 0
    free_cash   = income - expenses - total_emi_b

    flags = []

    flags.append(flag("warning","🧾",
        f"Registration & stamp duty ≈7% adds ₹{hidden_costs:,.0f}. Actual cost: ₹{actual_cost:,.0f}."))
    flags.append(flag("warning","🔒",
        "Plots are illiquid — selling may take months to years. Don't lock capital you may need urgently."))

    loc_msgs = {
        "urban":    ("Strong demand and ~8%/yr appreciation expected.", "success"),
        "suburban": ("Growing area — moderate appreciation (~6%/yr).", "success"),
        "rural":    ("Low liquidity and ~4%/yr appreciation. Long holding period needed.", "warning"),
        "highway":  ("Commercial upside possible (~7%/yr) but dependent on infrastructure.", "warning"),
    }
    lm, ll = loc_msgs.get(loc_type,("Appreciation uncertain.", "warning"))
    flags.append(flag(ll,"📍",lm))

    flags.append(flag("success" if purpose=="construction" else "warning",
        "🏗️" if purpose=="construction" else "📈",
        ("Building adds utility and rental potential — productive use of land."
         if purpose=="construction" else
         "Investment plot yields returns only at resale. No income generated until sold.")))

    if savings_after < 0:
        flags.append(flag("danger","🛡️","Savings cannot cover the down payment."))
    elif savings_after < ef_needed:
        flags.append(flag("warning","🛡️",
            f"₹{savings_after:,.0f} after payment — below 6-month fund of ₹{ef_needed:,.0f}."))
    else:
        flags.append(flag("success","🛡️",f"₹{savings_after:,.0f} post-payment — emergency fund secure."))

    if dep_total > 0:
        flags.append(flag("warning" if dep_total > income*0.20 else "success","👨‍👩‍👧",
            f"Dependency obligations: ₹{dep_total:,.0f}/mo ({', '.join(exp_data['dep_names'])})."))

    if has_loan:
        if dti > 50:
            flags.append(flag("danger","📊",f"Loan EMI burden {dti:.1f}% — exceeds safe limit."))
        elif dti > 35:
            flags.append(flag("warning","📊",f"Loan EMI burden {dti:.1f}% — above comfortable range."))
        else:
            flags.append(flag("success","📊",f"Loan EMI burden {dti:.1f}% — within safe range."))

        income_80  = income * 0.80
        dti_stress = (total_emi_b / income_80 * 100)
        flags.append(flag("success" if dti_stress<=50 else "warning","⚡",
            f"Stress test: 20% income drop → EMI burden {dti_stress:.1f}%."))
    else:
        flags.append(flag("success","💰","Full cash purchase eliminates loan interest burden."))

    sm = stress_meter(income, expenses, monthly_emi, existing, savings, savings_after, ef_needed)

    verdicts = []
    if savings_after < 0:           verdicts.append("NOT_RECOMMENDED")
    elif savings_after < ef_needed: verdicts.append("RISKY")
    if has_loan:                    verdicts.append(dti_level(dti))
    if free_cash < 0:               verdicts.append("NOT_RECOMMENDED")

    decision = combine(*verdicts) if verdicts else "SAFE"
    summaries = {
        "SAFE":           "Your finances support this plot. Ensure full legal due diligence (title, encumbrance, approvals) before proceeding.",
        "RISKY":          "Possible but your savings buffer is thin. Plots are illiquid — ensure you won't need this capital soon.",
        "NOT_RECOMMENDED":"This purchase would severely deplete your savings. Build a larger corpus before investing."
    }

    return {
        "decision":      decision, "confidence":"Medium", "summary":summaries[decision],
        "flags":         flags, "timeline":[], "worst_month":None,
        "stress_meter":  sm,
        "top3_expenses": exp_data["top3"],
        "dep_names":     exp_data["dep_names"],
        "dep_total":     exp_data["dep_total"],
        "rent_vs_buy":   None,
        "metrics": {
            "loan_amount":   round(loan,2),
            "monthly_emi":   round(monthly_emi,2),
            "total_interest":round((total_payment-loan) if has_loan else 0,2),
            "actual_cost":   round(actual_cost,2),
            "hidden_costs":  round(hidden_costs,2),
            "savings_after": round(savings_after,2),
            "free_cash":     round(free_cash,2),
            "value_5yr":     value_5yr,
            "value_10yr":    value_10yr,
            "appr_pct":      round(appr_rate*100,0),
            "dti_ratio":     round(dti,1),
        },
        "alternative": {"show":False, "max_price":0, "max_emi":0}
    }


# ══════════════════════════════════════════════════
#  MAIN ANALYZE ENDPOINT
# ══════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/robots.txt")
def robots():
    return app.send_static_file("robots.txt")


@app.route("/sitemap.xml")
def sitemap():
    return app.send_static_file("sitemap.xml"), 200, {"Content-Type": "application/xml"}


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        d          = request.get_json()
        profile    = d.get("profile", {})
        asset      = d.get("asset", {})
        asset_type = d.get("asset_type", "house")
        expenses   = d.get("expenses", [])

        for f in ["monthly_income", "current_savings"]:
            if not profile.get(f):
                return jsonify({"error": f"Missing required field: {f}"}), 400

        exp_data = process_expenses(expenses)

        dispatch = {"house": analyze_house, "car": analyze_car, "plot": analyze_plot}
        if asset_type not in dispatch:
            return jsonify({"error": "Unknown asset type"}), 400

        result = dispatch[asset_type](profile, asset, exp_data)
        result["asset_type"] = asset_type
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
