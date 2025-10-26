import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO

# ============================================================
# 0. Session state init (to persist results across reruns)
# ============================================================
if "results_df" not in st.session_state:
    st.session_state["results_df"] = None

# ============================================================
# 1. Brand/domain map
# ============================================================
BRAND_DOMAINS = {
    "Action Network": "actionnetwork.com",
    "Vegas Insider": "vegasinsider.com",
    "RotoGrinders": "rotogrinders.com",
    "Canada Sports Betting": "canadasportsbetting.ca"
}

brand_options = ["All brands"] + list(BRAND_DOMAINS.keys())

# ============================================================
# 2. Streamlit Layout
# ============================================================
st.set_page_config(page_title="Anchor Text Extractor", layout="wide")
st.title("🔗 Anchor Text Extractor")

selected_brand = st.selectbox("Brand:", brand_options, index=0)

urls_input = st.text_area(
    "Paste one URL per line:",
    height=200,
    placeholder="https://example.com/article1\nhttps://example.com/article2"
)

urls = [line.strip() for line in urls_input.strip().splitlines() if line.strip()]
st.markdown(f"**URLs entered:** {len(urls)} / 100")

if len(urls) > 100:
    st.error(f"⚠️ Too many URLs entered ({len(urls)}). Please limit to 100 or fewer.")

# ============================================================
# 3. Helper: Fetch + Detect Removed
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
# 4. Extraction function
# ============================================================
def extract_anchors(urls, selected_brand):
    results = []
    progress_bar = st.progress(0)
    total = len(urls)

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
# 5. Status inference (for filtering only; not shown in table)
# ============================================================
def infer_status(row):
    at = str(row.get("Anchor Text", "") or "")
    pt = str(row.get("Page Title", "") or "")

    if at.startswith("❌ Page Removed / Content Unavailable"):
        return "Removed"
    if at == "No links found":
        return "No Links"
    if at.startswith("❌ No ") and at.endswith(" link found"):
        return "No Brand Link"
    if at.startswith("⚠️") or pt.startswith("⚠️"):
        return "Error"
    if at and not at.startswith(("❌", "⚠️")):
        return "Has Links"
    return "Unknown"

# ============================================================
# 6. Extract on click -> persist results; then show filters/views
# ============================================================
if st.button("🚀 Extract Anchor Texts"):
    if not urls:
        st.warning("⚠️ Please enter at least one URL.")
    elif len(urls) > 100:
        st.error("❌ Too many URLs entered.")
    else:
        st.session_state["results_df"] = extract_anchors(urls, selected_brand)

# If we have results saved, show controls and table (persists across reruns)
if st.session_state["results_df"] is not None and not st.session_state["results_df"].empty:
    df = st.session_state["results_df"].copy()
    df["_status"] = df.apply(infer_status, axis=1)

    # Downloads (full + filtered)
    csv_full = df.drop(columns=["_status"]).to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_full,
        file_name="anchor_text_results.csv",
        mime="text/csv"
    )

    # Filter UI (persist selection via key so it won’t reset unexpectedly)
    filt = st.selectbox(
        "Filter rows:",
        [
            "Show all",
            "Only Removed",
            "Hide Removed",
            "Only “No links found”",
            "Only Errors",
            "Only Rows With Links",
        ],
        index=0,
        key="row_filter_select",
        help="Filter by the computed status of each row. Results persist until you click Extract again."
    )

    df_view = df.copy()
    if filt == "Only Removed":
        df_view = df_view[df_view["_status"] == "Removed"]
    elif filt == "Hide Removed":
        df_view = df_view[df_view["_status"] != "Removed"]
    elif filt == "Only “No links found”":
        df_view = df_view[df_view["_status"] == "No Links"]
    elif filt == "Only Errors":
        df_view = df_view[df_view["_status"] == "Error"]
    elif filt == "Only Rows With Links":
        df_view = df_view[df_view["_status"] == "Has Links"]

    # Filtered CSV
    csv_filtered = df_view.drop(columns=["_status"]).to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered CSV",
        data=csv_filtered,
        file_name="anchor_text_results_filtered.csv",
        mime="text/csv"
    )

    st.success("✅ Extraction complete! (Results persist until you extract again.)")
    st.dataframe(df_view.drop(columns=["_status"]), use_container_width=True)
elif st.session_state["results_df"] is not None:
    st.warning("⚠️ No data extracted.")
