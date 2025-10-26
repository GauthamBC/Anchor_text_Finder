import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO
import streamlit.components.v1 as components  # NEW: for copy-to-clipboard

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
# 5. Run extraction + Show results
# ============================================================
if st.button("🚀 Extract Anchor Texts"):
    if not urls:
        st.warning("⚠️ Please enter at least one URL.")
    elif len(urls) > 100:
        st.error("❌ Too many URLs entered.")
    else:
        df = extract_anchors(urls, selected_brand)

        if not df.empty:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name="anchor_text_results.csv",
                mime="text/csv"
            )

            st.success("✅ Extraction complete!")
            st.dataframe(df, use_container_width=True)

            # ============================================================
            # Copy Anchors (Row-aligned for Sheets) + real clipboard button
            # ============================================================
            if st.button("📋 Copy Anchor Text (Sheet-Friendly)"):
                lines = []
                for _, row in df.iterrows():
                    cell = str(row.get("Anchor Text", "")).strip()

                    if (
                        not cell
                        or cell.startswith("❌")
                        or cell.startswith("⚠️")
                        or cell == "No links found"
                    ):
                        lines.append("")  # Blank row to preserve alignment
                    else:
                        parts = [p.strip() for p in cell.split(";") if p.strip()]
                        lines.append("; ".join(parts))

                # Use CRLF to be extra-friendly with clipboard parsers
                output_text = "\r\n".join(lines)

                # Visible preview
                st.text_area(
                    "✅ Copy preview (one line per URL). Tip: single-click a cell in Google Sheets, then paste:",
                    output_text,
                    height=220
                )

                # Real copy-to-clipboard button via a small HTML component
                components.html(f"""
                <div style="margin:8px 0 12px 0;">
                  <button id="copybtn" style="
                      padding:8px 12px;border-radius:8px;border:1px solid #ccc;cursor:pointer;">
                      Copy to Clipboard
                  </button>
                  <span id="status" style="margin-left:8px;color:#16a34a;"></span>
                  <textarea id="payload" style="position:absolute;left:-9999px;top:-9999px;">{output_text}</textarea>
                </div>
                <script>
                  const btn = document.getElementById('copybtn');
                  const status = document.getElementById('status');
                  btn.addEventListener('click', async () => {{
                    try {{
                      const text = document.getElementById('payload').value;
                      await navigator.clipboard.writeText(text);
                      status.textContent = 'Copied!';
                      setTimeout(() => status.textContent = '', 1500);
                    }} catch (e) {{
                      status.textContent = 'Press Ctrl/Cmd+C to copy';
                      setTimeout(() => status.textContent = '', 2000);
                    }}
                  }});
                </script>
                """, height=60)

        else:
            st.warning("⚠️ No data extracted.")
