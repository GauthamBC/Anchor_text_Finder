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

# Add "All brands"
brand_options = ["All brands"] + list(BRAND_DOMAINS.keys())

# ============================================================
# 2. Streamlit Layout
# ============================================================
st.set_page_config(page_title="Anchor Text Extractor", layout="wide")
st.title("🔗 Anchor Text Extractor")

# Dropdown
selected_brand = st.selectbox("Brand:", brand_options, index=0)

# URL input
urls_input = st.text_area(
    "Paste one URL per line:",
    height=200,
    placeholder="https://example.com/article1\nhttps://example.com/article2"
)

# Count + Limit notice
urls = [line.strip() for line in urls_input.strip().splitlines() if line.strip()]
st.markdown(f"**URLs entered:** {len(urls)}")
st.markdown(
    "<b style='color:#ffa500;'>⚠️ Please enter a maximum of 100 URLs per run.</b>",
    unsafe_allow_html=True
)

# ============================================================
# 3. Extraction function
# ============================================================
def extract_anchors(urls, selected_brand):
    results = []

    if selected_brand == "All brands":
        for url in urls:
            row = {"Source URL": url}
            all_anchors = []
            try:
                res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(res.text, "html.parser")

                # Page title
                row["Page Title"] = soup.title.string.strip() if soup.title and soup.title.string else "(No title found)"

                # Loop over brands
                for brand, domain in BRAND_DOMAINS.items():
                    anchor_texts = []
                    for a in soup.find_all("a", href=True):
                        if domain in a["href"]:
                            text = a.get_text(strip=True)
                            if text:
                                anchor_texts.append(text)
                    if anchor_texts:
                        row[brand] = "; ".join(anchor_texts)
                        all_anchors.extend(anchor_texts)
                    else:
                        row[brand] = f"❌ No {domain} link found"

                # Add combined summary
                row["Anchor Text"] = "; ".join(all_anchors) if all_anchors else "No links found"

            except Exception as e:
                for brand in BRAND_DOMAINS:
                    row[brand] = f"⚠️ Error: {str(e)}"
                row["Anchor Text"] = f"⚠️ Error: {str(e)}"
                row["Page Title"] = f"⚠️ Error: {str(e)}"

            results.append(row)

    else:
        domain = BRAND_DOMAINS[selected_brand]
        for url in urls:
            try:
                res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(res.text, "html.parser")

                page_title = soup.title.string.strip() if soup.title and soup.title.string else "(No title found)"
                anchor_texts = []
                for a in soup.find_all("a", href=True):
                    if domain in a["href"]:
                        text = a.get_text(strip=True)
                        if text:
                            anchor_texts.append(text)

                if anchor_texts:
                    results.append({
                        "Source URL": url,
                        "Anchor Texts": "; ".join(anchor_texts),
                        "Page Title": page_title
                    })
                else:
                    results.append({
                        "Source URL": url,
                        "Anchor Texts": f"❌ No {domain} link found",
                        "Page Title": page_title
                    })
            except Exception as e:
                results.append({
                    "Source URL": url,
                    "Anchor Texts": f"⚠️ Error: {str(e)}",
                    "Page Title": f"⚠️ Error: {str(e)}"
                })
    return pd.DataFrame(results)

# ============================================================
# 4. Run extraction + Show results
# ============================================================
if st.button("🚀 Extract Anchor Texts"):
    if not urls:
        st.warning("⚠️ Please enter at least one URL.")
    elif len(urls) > 100:
        st.error(f"Too many URLs entered ({len(urls)}). Please limit to 100 or fewer.")
    else:
        df = extract_anchors(urls, selected_brand)

        if not df.empty:
            st.success("✅ Extraction complete!")
            st.dataframe(df, use_container_width=True)

            # Download button
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name="anchor_text_results.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ No data extracted.")
