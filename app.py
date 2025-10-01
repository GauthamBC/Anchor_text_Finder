import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO

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
# 3. Extraction function
# ============================================================
def extract_anchors(urls, selected_brand):
    results = []
    progress_bar = st.progress(0)
    total = len(urls)

    if selected_brand == "All brands":
        for i, url in enumerate(urls, start=1):
            row = {"Source URL": url}
            all_anchors = []
            try:
                res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(res.text, "html.parser")

                row["Page Title"] = soup.title.string.strip() if soup.title and soup.title.string else "(No title found)"

                for brand, domain in BRAND_DOMAINS.items():
                    for a in soup.find_all("a", href=True):
                        if domain in a["href"]:
                            text = a.get_text(strip=True)
                            if text:
                                all_anchors.append(text)

                row["Anchor Text"] = "; ".join(all_anchors) if all_anchors else "No links found"

            except Exception as e:
                row["Page Title"] = f"⚠️ Error: {str(e)}"
                row["Anchor Text"] = f"⚠️ Error: {str(e)}"

            results.append(row)
            progress_bar.progress(i / total)

    else:
        domain = BRAND_DOMAINS[selected_brand]
        for i, url in enumerate(urls, start=1):
            row = {"Source URL": url}
            try:
                res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(res.text, "html.parser")

                row["Page Title"] = soup.title.string.strip() if soup.title and soup.title.string else "(No title found)"
                anchors = [a.get_text(strip=True) for a in soup.find_all("a", href=True) if domain in a["href"] and a.get_text(strip=True)]
                row["Anchor Text"] = "; ".join(anchors) if anchors else f"❌ No {domain} link found"

            except Exception as e:
                row["Page Title"] = f"⚠️ Error: {str(e)}"
                row["Anchor Text"] = f"⚠️ Error: {str(e)}"

            results.append(row)
            progress_bar.progress(i / total)

    return pd.DataFrame(results, columns=["Source URL", "Page Title", "Anchor Text"])

# ============================================================
# 4. Run extraction + Show results
# ============================================================
if st.button("🚀 Extract Anchor Texts"):
    if not urls:
        st.warning("⚠️ Please enter at least one URL.")
    elif len(urls) > 100:
        st.error("❌ Too many URLs entered.")
    else:
        df = extract_anchors(urls, selected_brand)

        if not df.empty:
            # Download button at the top
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name="anchor_text_results.csv",
                mime="text/csv"
            )

            st.success("✅ Extraction complete!")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("⚠️ No data extracted.")
