import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from collections import OrderedDict
import streamlit as st
import pandas as pd

def get_subpages(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a')
    subpages = [urljoin(url, link.get('href').split('#')[0]) for link in links if link.get('href') and '#' not in link.get('href')]
    return subpages

def search_goo_gl_urls(url, domain):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return [], f"エラー: {str(e)}"

    soup = BeautifulSoup(response.text, 'html.parser')
    goo_gl_pattern = re.compile(r'https://goo\.gl/\S+')
    goo_gl_urls = goo_gl_pattern.findall(str(soup))

    # ドメインの直下にあるページのみ検索
    parsed_url = urlparse(url)
    if parsed_url.netloc != domain:
        return [], None

    return list(set(goo_gl_urls)), ''

def process_urls(urls):
    results = OrderedDict()
    for url in urls:
        url = url.strip()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        if not domain:
            continue  # ドメインが含まれていない場合はスキップ

        if domain not in results:
            results[domain] = {"URL": url, "goo.gl URLs": [], "エラー": '', "サイトURL": set()}

        # メインページの検索
        main_goo_gl_urls, error = search_goo_gl_urls(url, domain)
        if error:
            results[domain]["エラー"] = error
        else:
            results[domain]["goo.gl URLs"].extend(main_goo_gl_urls)

        # 下層ページの検索
        subpages = get_subpages(url)
        for subpage in subpages:
            parsed_subpage = urlparse(subpage)
            if parsed_subpage.netloc == domain:
                subpage_goo_gl_urls, _ = search_goo_gl_urls(subpage, domain)
                results[domain]["goo.gl URLs"].extend(subpage_goo_gl_urls)
                if subpage_goo_gl_urls:
                    results[domain]["サイトURL"].add(subpage)

    return results

st.title('全ページ検索 goo.gl 検品ツール')
st.markdown('無料サーバーを使用しているためメモリ容量オーバーで強制終了が頻発しています。  \n検索件数1～3件でご使用くださいませ。')
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
        else:
            st.warning("goo.glリンクは見つかりませんでした。")
        
        csv = df.to_csv().encode('utf-8')
        st.download_button(
            label="結果をCSVでダウンロード",
            data=csv,
            file_name="goo_gl_search_results.csv",
            mime="text/csv",
        )
    else:
        st.warning('URLを少なくとも1つ入力してください。')