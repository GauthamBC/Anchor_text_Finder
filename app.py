import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO

# ============================================================
# 0) Persist results across reruns
# ============================================================
if "results_df" not in st.session_state:
    st.session_state["results_df"] = None

# ============================================================
# 1) Brand/domain map
# ============================================================
BRAND_DOMAINS = {
    "Action Network": "actionnetwork.com",
    "Vegas Insider": "vegasinsider.com",
    "RotoGrinders": "rotogrinders.com",
    "Canada Sports Betting": "canadasportsbetting.ca"
}
brand_options = ["All brands"] + list(BRAND_DOMAINS.keys())

# ============================================================
# 2) Layout
# ============================================================
st.set_page_config(page_title="Anchor Text Extractor", layout="wide")
st.title("🔗 Anchor Text Extractor")

# Use a form so editing inputs doesn't wipe results
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

if len(urls) > 100:
    st.error(f"⚠️ Too many URLs entered ({len(urls)}). Please limit to 100 or fewer.")

# ============================================================
# 3) Helper: Fetch + Detect Removed
# ============================================================
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

# ============================================================
# 4) Extraction
# ============================================================
def extract_anchors(urls, selected_brand):
    results = []
    progress_bar = st.progress(0)
    total = max(1, len(urls))

    for i, url in enumerate(urls, start=1):
        row = {"Source URL": url}
        title, soup, removed = fetch_page(url)

        if removed or soup is None:
            row["Page Title"] = "❌ Page Removed / Content Unavailable"
            row["Anchor Text"] = "❌ Page Removed / Content Unavailable"
            results.append(row)
            progress_bar.progress(i / total)
            continue

        row["Page Title"] = title

        try:
            if selected_brand == "All brands":
                anchor_list = []
                for brand, domain in BRAND_DOMAINS.items():
                    for a in soup.find_all("a", href=True):
                        if domain in a["href"]:
                            text = a.get_text(strip=True)
                            if text:
                                anchor_list.append(text)
                row["Anchor Text"] = "; ".join(anchor_list) if anchor_list else "No links found"
            else:
                domain = BRAND_DOMAINS[selected_brand]
                anchors = [
                    a.get_text(strip=True) for a in soup.find_all("a", href=True)
                    if domain in a["href"] and a.get_text(strip=True)
                ]
                row["Anchor Text"] = "; ".join(anchors) if anchors else f"❌ No {domain} link found"

        except Exception as e:
            row["Page Title"] = "⚠️ Error Processing Page"
            row["Anchor Text"] = f"⚠️ {str(e)}"

        results.append(row)
        progress_bar.progress(i / total)

    return pd.DataFrame(results, columns=["Source URL", "Page Title", "Anchor Text"])

# ============================================================
# 5) Run extraction (persist results)
# ============================================================
if submitted:
    if not urls:
        st.warning("⚠️ Please enter at least one URL.")
    elif len(urls) <= 100:
        st.session_state["results_df"] = extract_anchors(urls, selected_brand)

# ============================================================
# 6) Filters & table (results persist while you change filters)
# ============================================================
df = st.session_state["results_df"]
if df is not None and not df.empty:
    # Build masks once
    anchor_series = df["Anchor Text"].astype(str)
    is_removed = anchor_series.str.startswith("❌ Page Removed / Content Unavailable")
    is_no_links = anchor_series.eq("No links found")

    # Filter UI — only the four you wanted
    filt = st.selectbox(
        "Filter rows:",
        ["Show all", "Only Removed", 'Only "No links found"', "Hide Removed"],
        index=0,
        key="row_filter_select",
        help="Results persist until you click Extract again."
    )

    df_view = df.copy()
    if filt == "Only Removed":
        df_view = df_view[is_removed]
    elif filt == 'Only "No links found"':
        df_view = df_view[is_no_links]
    elif filt == "Hide Removed":
        df_view = df_view[~is_removed]
    # else: Show all

    # SIDE-BY-SIDE DOWNLOAD BUTTONS
    c1, c2 = st.columns(2)
    with c1:
        csv_full = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", data=csv_full, file_name="anchor_text_results.csv", mime="text/csv")
    with c2:
        csv_filtered = df_view.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Filtered CSV", data=csv_filtered, file_name="anchor_text_results_filtered.csv", mime="text/csv")

    st.success("✅ Extraction complete! (Results persist until you extract again.)")
    st.dataframe(df_view, use_container_width=True)

    # --------------------------------------------------------
    # Copy Column control (works with the CURRENT FILTER)
    # --------------------------------------------------------
    st.markdown("**Copy a column (respects current filter):**")
    col_to_copy = st.selectbox("Choose column to copy:", df_view.columns.tolist(), index=2, key="copy_col_select")
    include_header = st.checkbox("Include header in first line", value=False, key="copy_include_header")

    if st.button("📋 Copy selected column"):
        series = df_view[col_to_copy]
        lines = []  # one line per row, preserving order and blanks
        if include_header:
            lines.append(str(col_to_copy))
        for v in series.tolist():
            if v is None or (isinstance(v, float) and pd.isna(v)):
                lines.append("")
            else:
                lines.append(str(v))
        output_text = "\r\n".join(lines)  # CRLF helps Sheets

        # Use st.code for built-in copy icon
        st.code(output_text, language="text")
        st.caption("Tip: click the copy icon, then single-click the target cell in Sheets (don’t enter edit mode) and paste.")
elif df is not None:
    st.warning("⚠️ No data extracted.")
