import sqlite3
import json
from datetime import date

import streamlit as st

DB_PATH = "networth.db"

# -----------------------------
# 1. DATA MODEL / FIELD SCHEMAS
# -----------------------------

# For each subcategory we define extra structured fields beyond the common ones.
# Common fields stored for every entry:
# - kind: "asset" or "liability"
# - category
# - subcategory
# - name (main label)
# - currency
# - amount (value / outstanding)
# - owner
# - details_json (for extra fields)

ASSET_SCHEMAS = {
    "Cash & Cash-like": {
        "Cash (local currency)": [
            ("bank", "Bank / provider", "text"),
            ("account_type", "Account type", "select:Current,Savings"),
            ("account_nickname", "Account nickname", "text"),
            ("account_number", "Account number (masked)", "text"),
            ("interest_rate", "Interest rate (%)", "number"),
            ("liquidity", "Liquidity", "select:Instant,1-3 days,Term"),
        ],
        "Cash (foreign currency)": [
            ("bank", "Bank / provider", "text"),
            ("country", "Country", "text"),
            ("currency_held", "Currency held", "text"),
            ("account_nickname", "Account nickname", "text"),
        ],
        "Savings / Deposit account": [
            ("bank", "Bank / provider", "text"),
            ("account_type", "Account type", "select:Savings,Fixed/Term"),
            ("tenor", "Tenor / lock-in (months)", "number"),
            ("maturity_date", "Maturity date", "date"),
            ("interest_rate", "Interest rate (%)", "number"),
        ],
        "Money market / cash fund": [
            ("provider", "Fund / provider", "text"),
            ("isin", "ISIN / code", "text"),
        ],
    },
    "Listed Investments": {
        "Direct stocks / equities": [
            ("ticker", "Ticker", "text"),
            ("exchange", "Exchange / market", "text"),
            ("broker", "Broker / platform", "text"),
            ("shares", "Number of shares", "number"),
            ("purchase_price", "Average purchase price per share", "number"),
            ("purchase_date", "Main purchase date", "date"),
            ("current_price", "Current price per share", "number"),
        ],
        "Index funds / ETFs": [
            ("ticker", "Ticker", "text"),
            ("exchange", "Exchange", "text"),
            ("units", "Units held", "number"),
            ("purchase_price", "Average purchase price per unit", "number"),
            ("current_price", "Current price per unit", "number"),
        ],
        "Mutual funds / unit trusts": [
            ("fund_name", "Fund name", "text"),
            ("isin", "ISIN / code", "text"),
            ("units", "Units held", "number"),
            ("nav", "Latest NAV per unit", "number"),
            ("statement_date", "Latest statement date", "date"),
        ],
        "REITs": [
            ("ticker", "Ticker", "text"),
            ("exchange", "Exchange", "text"),
            ("units", "Units held", "number"),
            ("current_price", "Current price per unit", "number"),
            ("yield_pct", "Distribution yield (%)", "number"),
        ],
    },
    "Real Estate & Land": {
        "Primary residence": [
            ("country", "Country", "text"),
            ("city", "City/Region", "text"),
            ("address", "Full address", "text"),
            ("registration_no", "Title / registration / survey number", "text"),
            ("property_type", "Property type", "select:Condo,House,Apartment,Other"),
            ("tenure", "Tenure", "select:Freehold,99-year,Leasehold,Other"),
            ("area_sqft", "Area (sq ft)", "number"),
            ("acquisition_date", "Acquisition date", "date"),
            ("purchase_price", "Purchase price", "number"),
        ],
        "Investment property": [
            ("country", "Country", "text"),
            ("city", "City/Region", "text"),
            ("address", "Full address", "text"),
            ("registration_no", "Title / registration / survey number", "text"),
            ("property_type", "Property type", "select:Condo,Shop,Office,Warehouse,Other"),
            ("tenure", "Tenure", "select:Freehold,99-year,Leasehold,Other"),
            ("area_sqft", "Area (sq ft)", "number"),
            ("acquisition_date", "Acquisition date", "date"),
            ("purchase_price", "Purchase price", "number"),
            ("annual_rent", "Annual gross rent", "number"),
        ],
        "Land plot": [
            ("country", "Country", "text"),
            ("city", "City/Region", "text"),
            ("location_desc", "Location description", "text"),
            ("survey_no", "Survey / plot number", "text"),
            ("area_sqft", "Area (sq ft)", "number"),
        ],
    },
    "Retirement & Employment-linked": {
        "Public pension / provident": [
            ("scheme_name", "Scheme name (e.g. CPF, EPF)", "text"),
            ("account_id", "Member / account ID", "text"),
            ("retirement_age", "Retirement age", "number"),
        ],
        "401k / occupational plan": [
            ("plan_name", "Plan name", "text"),
            ("provider", "Plan provider", "text"),
            ("account_id", "Account ID", "text"),
            ("vested_pct", "Vested %", "number"),
        ],
        "Gratuity / end-of-service": [
            ("employer", "Employer", "text"),
            ("country", "Country", "text"),
            ("years_service", "Years of service", "number"),
        ],
        "Stock options / RSUs": [
            ("employer", "Employer", "text"),
            ("plan_type", "Plan type", "select:RSU,Option,ESPP,PSU"),
            ("grant_date", "Grant date", "date"),
            ("vesting_schedule", "Vesting schedule (text)", "text"),
        ],
    },
    "Insurance Assets": {
        "Whole life / UL policy": [
            ("insurer", "Insurer", "text"),
            ("policy_number", "Policy number", "text"),
            ("life_assured", "Life assured", "text"),
            ("sum_assured", "Sum assured / face value", "number"),
            ("start_date", "Policy start date", "date"),
            ("maturity_date", "Maturity date (if any)", "date"),
        ],
        "Endowment policy": [
            ("insurer", "Insurer", "text"),
            ("policy_number", "Policy number", "text"),
            ("maturity_date", "Maturity date", "date"),
        ],
        "Investment-linked policy (ILP)": [
            ("insurer", "Insurer", "text"),
            ("policy_number", "Policy number", "text"),
            ("fund_allocation", "Funds allocation (summary)", "text"),
        ],
        "Annuity": [
            ("insurer", "Insurer", "text"),
            ("start_date", "Payout start date", "date"),
            ("payout_amount", "Periodic payout amount", "number"),
        ],
    },
    "Private Market Investments": {
        "PE / VC fund": [
            ("fund_name", "Fund name", "text"),
            ("manager", "Manager / GP", "text"),
            ("vehicle_type", "Vehicle type", "select:PE Fund,VC Fund,Private Credit,Hedge Fund"),
            ("commitment", "Total commitment", "number"),
            ("capital_called", "Capital called to date", "number"),
            ("distributions", "Distributions received", "number"),
            ("vintage_year", "Vintage year", "number"),
        ],
        "Direct / co-investment": [
            ("company", "Company / asset name", "text"),
            ("jurisdiction", "Jurisdiction", "text"),
            ("stake_pct", "Stake %", "number"),
            ("capital_invested", "Capital invested", "number"),
        ],
    },
    "Business & Professional Interests": {
        "Private company shares": [
            ("company", "Company name", "text"),
            ("jurisdiction", "Jurisdiction", "text"),
            ("entity_type", "Entity type", "text"),
            ("stake_pct", "Stake %", "number"),
        ],
        "Partnership / LLP interest": [
            ("entity_name", "Entity name", "text"),
            ("role", "Role (Partner / Member)", "text"),
        ],
        "Franchise rights": [
            ("brand", "Franchise brand", "text"),
            ("territory", "Territory", "text"),
        ],
    },
    "Digital & Crypto Assets": {
        "Cryptocurrency": [
            ("token", "Token (e.g. BTC, ETH)", "text"),
            ("wallet", "Wallet / exchange", "text"),
            ("quantity", "Quantity", "number"),
            ("reference_price", "Reference price", "number"),
        ],
        "NFT / digital collectible": [
            ("collection", "Collection / project", "text"),
            ("token_id", "Token ID", "text"),
            ("platform", "Platform", "text"),
        ],
        "Website / online business": [
            ("url", "Website / platform URL", "text"),
            ("last12_rev", "Last 12m revenue", "number"),
        ],
    },
    "Luxury & Collectible Assets": {
        "Art / painting": [
            ("artist", "Artist", "text"),
            ("title", "Title of work", "text"),
            ("year", "Year", "number"),
            ("certificate", "Certificate / provenance", "text"),
        ],
        "Watch / jewellery": [
            ("brand", "Brand", "text"),
            ("model", "Model / reference", "text"),
            ("serial", "Serial number", "text"),
        ],
        "Car / vehicle": [
            ("make", "Make", "text"),
            ("model", "Model", "text"),
            ("year", "Year", "number"),
            ("registration", "Registration number", "text"),
        ],
    },
    "Claims & Receivables": {
        "Loan to individual": [
            ("counterparty", "Borrower name", "text"),
            ("purpose", "Purpose", "text"),
            ("agreement_no", "Loan agreement reference", "text"),
            ("interest_rate", "Interest rate (%)", "number"),
            ("due_date", "Due date", "date"),
        ],
        "Loan to company": [
            ("counterparty", "Company name", "text"),
            ("purpose", "Purpose", "text"),
            ("interest_rate", "Interest rate (%)", "number"),
        ],
        "Tax refund receivable": [
            ("jurisdiction", "Jurisdiction", "text"),
            ("tax_year", "Tax year", "text"),
        ],
        "Security deposit": [
            ("counterparty", "Counterparty / landlord", "text"),
            ("purpose", "Purpose (rental, utilities, etc.)", "text"),
        ],
    },
}

LIABILITY_SCHEMAS = {
    "Home & Property Loans": {
        "Home mortgage (primary residence)": [
            ("lender", "Lender / bank", "text"),
            ("loan_type", "Loan type", "select:Amortising,Interest-only"),
            ("interest_rate", "Interest rate (%)", "number"),
            ("rate_type", "Rate type", "select:Fixed,Floating"),
            ("start_date", "Start date", "date"),
            ("maturity_date", "Maturity date", "date"),
            ("linked_property", "Linked property (name / ID)", "text"),
            ("monthly_instalment", "Monthly instalment", "number"),
        ],
        "Investment property loan": [
            ("lender", "Lender / bank", "text"),
            ("interest_rate", "Interest rate (%)", "number"),
            ("linked_property", "Linked property (name / ID)", "text"),
        ],
        "Construction / renovation loan": [
            ("lender", "Lender / bank", "text"),
            ("purpose", "Purpose", "text"),
        ],
    },
    "Personal Debt": {
        "Credit card": [
            ("issuer", "Issuer", "text"),
            ("card_last4", "Card number (last 4)", "text"),
            ("credit_limit", "Credit limit", "number"),
            ("apr", "Annual interest rate (%)", "number"),
            ("due_date", "Payment due date", "date"),
        ],
        "Personal loan": [
            ("lender", "Lender", "text"),
            ("purpose", "Purpose", "text"),
            ("interest_rate", "Interest rate (%)", "number"),
            ("start_date", "Start date", "date"),
            ("maturity_date", "Maturity date", "date"),
        ],
        "BNPL / instalment plan": [
            ("provider", "Provider", "text"),
            ("item", "Item / purchase", "text"),
            ("installment_amount", "Installment amount", "number"),
            ("last_payment_date", "Last payment date", "date"),
        ],
    },
    "Business & Professional Liabilities": {
        "Business term loan": [
            ("borrowing_entity", "Borrowing entity", "text"),
            ("lender", "Lender", "text"),
            ("interest_rate", "Interest rate (%)", "number"),
            ("maturity_date", "Maturity date", "date"),
            ("security", "Security / collateral", "text"),
        ],
        "Working capital / overdraft": [
            ("borrowing_entity", "Borrowing entity", "text"),
            ("lender", "Lender", "text"),
        ],
        "Trade finance": [
            ("borrowing_entity", "Borrowing entity", "text"),
            ("instrument_type", "Instrument type (LC, BG, etc.)", "text"),
        ],
    },
    "Investment & Trading Leverage": {
        "Margin loan": [
            ("broker", "Broker", "text"),
            ("account_id", "Account ID", "text"),
            ("collateral_value", "Collateral value", "number"),
        ],
        "Securities-backed lending": [
            ("bank", "Bank", "text"),
            ("facility_limit", "Facility limit", "number"),
        ],
    },
    "Tax Liabilities": {
        "Income tax payable": [
            ("jurisdiction", "Jurisdiction", "text"),
            ("tax_year", "Tax year", "text"),
            ("due_date", "Due date", "date"),
        ],
        "Capital gains tax": [
            ("jurisdiction", "Jurisdiction", "text"),
            ("tax_year", "Tax year", "text"),
        ],
        "Property tax": [
            ("jurisdiction", "Jurisdiction", "text"),
            ("property_ref", "Property reference", "text"),
        ],
    },
    "Deferred & Instalment Obligations": {
        "Instalment purchase": [
            ("counterparty", "Counterparty", "text"),
            ("item", "Item / service", "text"),
        ],
        "Deferred purchase price": [
            ("counterparty", "Counterparty", "text"),
            ("description", "Description", "text"),
        ],
    },
    "Other Payables & Accrued Expenses": {
        "Accrued expense": [
            ("counterparty", "Counterparty", "text"),
            ("description", "Description", "text"),
        ],
        "Unpaid rent / utilities": [
            ("counterparty", "Counterparty", "text"),
            ("period", "Period", "text"),
        ],
    },
}

# Flatten category lists for UI
ASSET_CATEGORIES = list(ASSET_SCHEMAS.keys())
LIABILITY_CATEGORIES = list(LIABILITY_SCHEMAS.keys())


# -----------------------------
# 2. DATABASE HELPERS
# -----------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,              -- 'asset' or 'liability'
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            name TEXT NOT NULL,
            currency TEXT,
            amount REAL NOT NULL,
            owner TEXT,
            details_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def insert_entry(kind, category, subcategory, name, currency, amount, owner, details):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO entries (kind, category, subcategory, name, currency, amount, owner, details_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (kind, category, subcategory, name, currency, amount, owner, json.dumps(details)),
    )
    conn.commit()
    conn.close()


def get_totals():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) FROM entries WHERE kind='asset'")
    total_assets = c.fetchone()[0] or 0.0
    c.execute("SELECT COALESCE(SUM(amount),0) FROM entries WHERE kind='liability'")
    total_liabilities = c.fetchone()[0] or 0.0
    conn.close()
    return total_assets, total_liabilities


def get_entries(kind=None, category=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT id, kind, category, subcategory, name, currency, amount, owner, details_json, created_at FROM entries WHERE 1=1"
    params = []
    if kind:
        query += " AND kind=?"
        params.append(kind)
    if category:
        query += " AND category=?"
        params.append(category)
    query += " ORDER BY created_at DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows


# -----------------------------
# 3. FORM RENDERING
# -----------------------------

def render_detail_fields(schema):
    """
    schema: list of (field_name, label, type_str)
    Returns dict of values for each field_name.
    """
    values = {}
    for field_name, label, type_str in schema:
        if type_str.startswith("select:"):
            options = type_str.split(":", 1)[1].split(",")
            values[field_name] = st.selectbox(label, options, key=f"{field_name}_{label}")
        elif type_str == "text":
            values[field_name] = st.text_input(label, key=f"{field_name}_{label}")
        elif type_str == "number":
            values[field_name] = st.number_input(label, key=f"{field_name}_{label}", step=1.0, format="%.4f")
        elif type_str == "date":
            d = st.date_input(label, key=f"{field_name}_{label}", value=date.today())
            values[field_name] = d.isoformat() if isinstance(d, date) else str(d)
        else:
            values[field_name] = st.text_input(label, key=f"{field_name}_{label}")
    return values


# -----------------------------
# 4. STREAMLIT UI
# -----------------------------

def main():
    st.set_page_config(page_title="Net Worth Tracker", layout="wide")
    st.title("Net Worth Tracker (Python + SQLite)")

    init_db()

    view = st.sidebar.radio("View", ["Dashboard", "Assets", "Liabilities"])

    # DASHBOARD
    if view == "Dashboard":
        total_assets, total_liabilities = get_totals()
        net_worth = total_assets - total_liabilities

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Assets", f"{total_assets:,.2f}")
        col2.metric("Total Liabilities", f"{total_liabilities:,.2f}")
        col3.metric("Net Worth", f"{net_worth:,.2f}")

        st.markdown("### Recent Entries")
        rows = get_entries()
        if rows:
            for r in rows[:20]:
                id_, kind, category, subcat, name, cur, amt, owner, details_json, created_at = r
                with st.expander(f"[{kind.upper()}] {name} ({category} / {subcat}) - {amt:,.2f} {cur or ''}"):
                    st.write(f"Owner: {owner or '-'}")
                    st.write(f"Created at: {created_at}")
                    if details_json:
                        try:
                            details = json.loads(details_json)
                        except Exception:
                            details = {}
                        if details:
                            st.write("Details:")
                            st.json(details)
        else:
            st.info("No entries yet. Go to Assets or Liabilities to start adding data.")

    # ASSETS
    elif view == "Assets":
        st.header("Assets")
        category = st.selectbox("Category", ASSET_CATEGORIES)
        subcats = list(ASSET_SCHEMAS[category].keys())
        subcategory = st.selectbox("Subcategory", subcats)

        st.subheader(f"Add Asset – {category} / {subcategory}")
        with st.form("asset_form"):
            name = st.text_input("Asset name / label (e.g. 'DBS SGD savings', 'Apple Inc. shares')")

            col1, col2, col3 = st.columns(3)
            currency = col1.text_input("Currency (e.g. SGD, USD, EUR)", value="SGD")
            owner = col2.text_input("Owner (You / Spouse / Joint / Trust / Co)", value="You")
            amount = col3.number_input("Current value / balance", min_value=0.0, step=1.0, format="%.2f")

            st.markdown("**Additional details** (for this subcategory)")
            schema = ASSET_SCHEMAS[category][subcategory]
            details = render_detail_fields(schema)

            submitted = st.form_submit_button("Save asset")
            if submitted:
                if not name:
                    st.error("Please provide an Asset name / label.")
                elif amount <= 0:
                    st.error("Amount must be greater than 0.")
                else:
                    insert_entry(
                        "asset",
                        category,
                        subcategory,
                        name,
                        currency,
                        amount,
                        owner,
                        details,
                    )
                    st.success("Asset saved successfully.")

        st.markdown("### Existing assets in this category")
        rows = get_entries(kind="asset", category=category)
        if rows:
            for r in rows:
                id_, kind, cat, subcat, name, cur, amt, owner, details_json, created_at = r
                if subcat != subcategory:
                    continue
                with st.expander(f"{name} – {amt:,.2f} {cur or ''}"):
                    st.write(f"Subcategory: {subcat}")
                    st.write(f"Owner: {owner or '-'}")
                    st.write(f"Created at: {created_at}")
                    if details_json:
                        try:
                            details = json.loads(details_json)
                        except Exception:
                            details = {}
                        if details:
                            st.write("Details:")
                            st.json(details)
        else:
            st.info("No assets recorded yet for this category.")

    # LIABILITIES
    elif view == "Liabilities":
        st.header("Liabilities")
        category = st.selectbox("Category", list(LIABILITY_SCHEMAS.keys()))
        subcats = list(LIABILITY_SCHEMAS[category].keys())
        subcategory = st.selectbox("Subcategory", subcats)

        st.subheader(f"Add Liability – {category} / {subcategory}")
        with st.form("liab_form"):
            name = st.text_input("Liability name / label (e.g. 'Home loan – OCBC', 'Credit card – HSBC')")

            col1, col2, col3 = st.columns(3)
            currency = col1.text_input("Currency (e.g. SGD, USD, EUR)", value="SGD")
            owner = col2.text_input("Borrower / owner (You / Spouse / Joint / Co / Trust)", value="You")
            amount = col3.number_input("Outstanding amount", min_value=0.0, step=1.0, format="%.2f")

            st.markdown("**Additional details** (for this subcategory)")
            schema = LIABILITY_SCHEMAS[category][subcategory]
            details = render_detail_fields(schema)

            submitted = st.form_submit_button("Save liability")
            if submitted:
                if not name:
                    st.error("Please provide a Liability name / label.")
                elif amount <= 0:
                    st.error("Outstanding amount must be greater than 0.")
                else:
                    insert_entry(
                        "liability",
                        category,
                        subcategory,
                        name,
                        currency,
                        amount,
                        owner,
                        details,
                    )
                    st.success("Liability saved successfully.")

        st.markdown("### Existing liabilities in this category")
        rows = get_entries(kind="liability", category=category)
        if rows:
            for r in rows:
                id_, kind, cat, subcat, name, cur, amt, owner, details_json, created_at = r
                if subcat != subcategory:
                    continue
                with st.expander(f"{name} – {amt:,.2f} {cur or ''}"):
                    st.write(f"Subcategory: {subcat}")
                    st.write(f"Owner: {owner or '-'}")
                    st.write(f"Created at: {created_at}")
                    if details_json:
                        try:
                            details = json.loads(details_json)
                        except Exception:
                            details = {}
                        if details:
                            st.write("Details:")
                            st.json(details)
        else:
            st.info("No liabilities recorded yet for this category.")


if __name__ == "__main__":
    main()
