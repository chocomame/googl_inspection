import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from collections import OrderedDict
import streamlit as st
import pandas as pd
import time

def timer(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return wrapper

@timer
def get_subpages(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching subpages for {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a')
    subpages = [urljoin(url, link.get('href').split('#')[0]) for link in links if link.get('href') and '#' not in link.get('href')]
    return list(set(subpages))  # 重複を除去

@timer
def search_goo_gl_urls(url, domain):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error searching goo.gl URLs for {url}: {e}")
        return [], f"エラー: {str(e)}"

    soup = BeautifulSoup(response.text, 'html.parser')
    goo_gl_pattern = re.compile(r'https?://goo\.gl/\S+')
    goo_gl_urls = goo_gl_pattern.findall(str(soup))

    parsed_url = urlparse(url)
    if parsed_url.netloc != domain:
        return [], None

    print(f"Found {len(goo_gl_urls)} goo.gl URLs on {url}")
    return list(set(goo_gl_urls)), ''

@timer
def process_subpages(subpages, domain, progress_bar, progress_text):
    goo_gl_urls = []
    site_urls = set()
    total_subpages = len(subpages)
    for i, subpage in enumerate(subpages):
        try:
            subpage_goo_gl_urls, _ = search_goo_gl_urls(subpage, domain)
            goo_gl_urls.extend(subpage_goo_gl_urls)
            if subpage_goo_gl_urls:
                site_urls.add(subpage)
        except Exception as exc:
            print(f'{subpage} generated an exception: {exc}')
        
        # Update progress
        progress = (i + 1) / total_subpages
        progress_bar.progress(progress)
        progress_text.text(f"サブページ処理中: {i+1}/{total_subpages}")
    return goo_gl_urls, site_urls

@timer
def process_url(url, progress_bar, progress_text):
    url = url.strip()
    parsed_url = urlparse(url)
    domain = parsed_url.netloc

    if not domain:
        return None

    result = {"URL": url, "goo.gl URLs": [], "エラー": '', "サイトURL": set()}

    progress_text.text(f"メインページ処理中: {url}")
    main_goo_gl_urls, error = search_goo_gl_urls(url, domain)
    if error:
        result["エラー"] = error
    else:
        result["goo.gl URLs"].extend(main_goo_gl_urls)

    progress_text.text(f"サブページ取得中: {url}")
    subpages = get_subpages(url)
    
    progress_text.text(f"サブページ処理中: {url}")
    subpage_goo_gl_urls, subpage_site_urls = process_subpages(subpages, domain, progress_bar, progress_text)
    result["goo.gl URLs"].extend(subpage_goo_gl_urls)
    result["サイトURL"].update(subpage_site_urls)

    return domain, result

@timer
def process_urls(urls):
    results = OrderedDict()
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    total_urls = len(urls)
    for i, url in enumerate(urls):
        try:
            progress_text.text(f"URL処理中 ({i+1}/{total_urls}): {url}")
            result = process_url(url, progress_bar, progress_text)
            if result:
                domain, data = result
                results[domain] = data
        except Exception as exc:
            print(f'{url} generated an exception: {exc}')
            results[url] = {"URL": url, "goo.gl URLs": [], "エラー": str(exc), "サイトURL": set()}
        
        # Update overall progress
        progress_bar.progress((i + 1) / total_urls)
    
    progress_text.text("処理完了")
    return results

# Streamlit UI
st.set_page_config(page_title='全ページ検索 goo.gl 検品ツール', page_icon='🔍')
st.title('全ページ検索 goo.gl 検品ツール')

st.markdown("""
<style>
.small-font {
    font-size:0.8em;
}
.big-font {
    font-size:1em;
}
.mb40{
    margin-bottom: 40px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<p class="big-font">
無料サーバーを使用しているためメモリ容量オーバーで強制終了が頻発しています。<br>検索件数1～3件でご使用くださいませ。</p>
<div class="small-font mb40">
※ 目視で進捗が分かるように調整しました。<br>
※ 少しだけ軽くするように調整しましたが、同時接続状況によっては再度強制終了になるかもしれないため、<br>　引き続き検索件数1～3件でお願いいたします。
</div>
""", unsafe_allow_html=True)

urls = st.text_area('調査するウェブサイトのURLを1行に1つずつ入力してください:')

if st.button('検索'):
    if urls:
        urls_list = [url.strip() for url in urls.split('\n') if url.strip()]
        with st.spinner('検索中...'):
            results = process_urls(urls_list)
        
        # 結果の表示
        if results:
            rows = []
            for domain, data in results.items():
                goo_gl_urls = '\n'.join(set(data['goo.gl URLs']))
                site_urls = '\n'.join(data['サイトURL'])
                row = {'ドメイン': domain, 'URL': data['URL'], 'goo.gl URLs': goo_gl_urls, 'サイトURL': site_urls, 'エラー': data['エラー']}
                rows.append(row)
            df = pd.DataFrame(rows)
            st.dataframe(df.style.set_properties(**{'text-align': 'left'}))
        
            csv = df.to_csv().encode('utf-8')
            st.download_button(
                label="結果をCSVでダウンロード",
                data=csv,
                file_name="goo_gl_search_results.csv",
                mime="text/csv",
            )
        else:
            st.warning("goo.glリンクは見つかりませんでした。")
    else:
        st.warning('URLを少なくとも1つ入力してください。')