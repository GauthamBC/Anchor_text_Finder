import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO

# =========================
# Session state (persist DF)
# =========================
if "results_df" not in st.session_state:
    st.session_state.results_df = None

# =========================
# 1) Brand/domain map
# =========================
BRAND_DOMAINS = {
    "Action Network": "actionnetwork.com",
    "Vegas Insider": "vegasinsider.com",
    "RotoGrinders": "rotogrinders.com",
    "Canada Sports Betting": "canadasportsbetting.ca"
}
brand_options = ["All brands"] + list(BRAND_DOMAINS.keys())

# =========================
# 2) Layout
# =========================
st.set_page_config(page_title="Anchor Text Extractor", layout="wide")
st.title("🔗 Anchor Text Extractor")

# Use a form so editing inputs doesn’t rerun extraction
with st.form("input_form", clear_on_submit=False):
    selected_brand = st.selectbox("Brand:", brand_options, index=0)
    urls_input = st.text_area(
        "Paste one URL per line:",
        height=200,
        placeholder="https://example.com/article1\nhttps://example.com/article2"
    )

    urls = [line.strip() for line in urls_input.strip().splitlines() if line.strip()]
    st.markdown(f"**URLs entered:** {len(urls)} / 100")

    submitted = st.form_submit_button("🚀 Extract Anchor Texts")

# =========================
# 3) Helper: Fetch + 404 detection
# =========================
def fetch_page(url):
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        status = res.status_code
        html = res.text

        if status == 404:
            return "(Removed / 404)", None, True

        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else "(No title found)"

        if "404" in title or "not found" in title.lower():
            return "(Removed / 404)", None, True

        if "isErrorPage" in html or '"template":"404"' in html or "Unable to locate the page" in html:
            return "(Removed / 404)", None, True

        return title, soup, False

    except Exception as e:
        return f"⚠️ Error: {str(e)}", None, False

# =========================
# 4) Extraction
# =========================
def extract_anchors(urls, selected_brand):
    results = []
    progress = st.progress(0)
    total = max(1, len(urls))

    for i, url in enumerate(urls, start=1):
        row = {"Source URL": url}
        title, soup, removed = fetch_page(url)

        if removed or soup is None:
            row["Page Title"] = "❌ Page Removed / Content Unavailable"
            row["Anchor Text"] = "❌ Page Removed / Content Unavailable"
            results.append(row)
            progress.progress(i / total)
            continue

        row["Page Title"] = title

        try:
            if selected_brand == "All brands":
                anchor_list = []
                for brand, domain in BRAND_DOMAINS.items():
                    for a in soup.find_all("a", href=True):
                        if domain in a["href"]:
                            txt = a.get_text(strip=True)
                            if txt:
                                anchor_list.append(txt)
                row["Anchor Text"] = "; ".join(anchor_list) if anchor_list else "No links found"
            else:
                domain = BRAND_DOMAINS[selected_brand]
                anchors = [
                    a.get_text(strip=True)
                    for a in soup.find_all("a", href=True)
                    if domain in a["href"] and a.get_text(strip=True)
                ]
                row["Anchor Text"] = "; ".join(anchors) if anchors else f"❌ No {domain} link found"
        except Exception as e:
            row["Page Title"] = "⚠️ Error Processing Page"
            row["Anchor Text"] = f"⚠️ {str(e)}"

        results.append(row)
        progress.progress(i / total)

    return pd.DataFrame(results, columns=["Source URL", "Page Title", "Anchor Text"])

# =========================
# 5) Status inference (for filters only)
# =========================
def infer_status(row):
    at = str(row.get("Anchor Text", "") or "")
    pt = str(row.get("Page Title", "") or "")
    if at.startswith("❌ Page Removed / Content Unavailable"):
        return "Removed"
    if at == "No links found":
        return "No Links"
    if at.startswith("❌ No ") and "link found" in at:
        return "No Brand Link"
    if at.startswith("⚠️") or pt.startswith("⚠️"):
        return "Error"
    if at and not at.startswith(("❌", "⚠️")):
        return "Has Links"
    return "Unknown"

# =========================
# 6) Run extraction (persist) when submitted
# =========================
if submitted:
    if not urls:
        st.warning("⚠️ Please enter at least one URL.")
    elif len(urls) > 100:
        st.error("❌ Too many URLs entered.")
    else:
        st.session_state.results_df = extract_anchors(urls, selected_brand)

# =========================
# 7) Filters & table (persist across reruns)
# =========================
df = st.session_state.results_df
if df is not None and not df.empty:
    df = df.copy()
    df["_status"] = df.apply(infer_status, axis=1)

    # Downloads
    csv_full = df.drop(columns=["_status"]).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv_full, file_name="anchor_text_results.csv", mime="text/csv")

    # Filter bar (won’t clear results)
    filt = st.selectbox(
        "Filter rows:",
        ["Show all", "Only Removed", "Hide Removed", "Only “No links found”", "Only Errors", "Only Rows With Links"],
        index=0,
        key="filter_select"
    )

    df_view = df
    if filt == "Only Removed":
        df_view = df[df["_status"] == "Removed"]
    elif filt == "Hide Removed":
        df_view = df[df["_status"] != "Removed"]
    elif filt == "Only “No links found”":
        df_view = df[df["_status"] == "No Links"]
    elif filt == "Only Errors":
        df_view = df[df["_status"] == "Error"]
    elif filt == "Only Rows With Links":
        df_view = df[df["_status"] == "Has Links"]

    # Optional: filtered download
    csv_filtered = df_view.drop(columns=["_status"]).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Filtered CSV", data=csv_filtered, file_name="anchor_text_results_filtered.csv", mime="text/csv")

    st.success("✅ Extraction complete! (Results persist until you run Extract again.)")
    st.dataframe(df_view.drop(columns=["_status"]), use_container_width=True)
elif df is not None:
    st.warning("⚠️ No data extracted.")
