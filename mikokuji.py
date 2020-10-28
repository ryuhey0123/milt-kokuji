import os
import glob
import webbrowser
import urllib.error
import urllib.request

import click
import requests
import inquirer
import pandas as pd
from bs4 import BeautifulSoup
from kanjize import int2kanji
from send2trash import send2trash


DOMAIN = 'https://www.mlit.go.jp'
INDEX_PAGE = '/notice/index.html'
HEADER_ROW = 2  # エクセルファイルのヘッダー行を指定

_DEFAULT_CACHE_DIR = os.path.join(os.getenv('HOME'), '.cache/mikokuji')


class Header:
    title = '告示・通達等の名称'
    number = '文書番号'
    date = '文書年月日'
    organization = '組織名'
    link = 'リンク'
    URL = 'URL'


@click.group()
def cmd():
    """国交省のウェブサイト(https://www.mlit.go.jp/notice/index.html)から告示を検索し、表示します"""
    pass


@cmd.command()
@click.argument('number', type=int)
def get(number):
    """告示を検索します。検索する告示番号を数字で入力してください"""

    user_cache_dir = os.getenv('MIKOKUJI_CACHE_DIR')
    cache_dir = user_cache_dir if user_cache_dir is not None else _DEFAULT_CACHE_DIR
    caches = glob.glob(cache_dir + '/**/*.xlsx', recursive=True)

    if not caches:
        click.echo("Cache is empty. Run 'mikokuji update'.")
        return 1

    latest_cache = max(caches, key=os.path.getctime)

    df = parse_xlsx(number, latest_cache)

    if df.empty:
        click.echo("Can't find number of {}. Please check input number.".format(number))
        return 0

    if len(df) == 1:
        click.echo("Found a result. Open at browser...")
        link = df[Header.URL].to_list()
        webbrowser.open(link[0])
        click.echo("Done.")
        return 1

    else:
        click.echo('Found some results. Please select yours.')
        questions = [
            inquirer.List(
                "result",
                choices=df[Header.title].to_list(),
            )
        ]
        result = inquirer.prompt(questions)['result']
        link = df[df[Header.title].str.contains(result)][Header.URL].to_list()
        webbrowser.open(link[0])
        click.echo("Done.")
        return 1


@cmd.command()
@click.option('--default', is_flag=True)
def update(default):
    """国交省のwebサイトから更新データを入手します"""

    res = requests.get(DOMAIN + INDEX_PAGE)
    soup = BeautifulSoup(res.content, 'html.parser')

    # <a></a>タグを全て抽出し、href属性を取り出す
    links = list(map(lambda x: x.get('href'), soup.find_all('a')))
    # 'xlsx'を含むリンクを検索
    xlsx_links = [s for s in links if 'xlsx' in s]

    if len(xlsx_links) >= 2:
        click.echo('Exist not one .xlsx files. Abort refresh.')
        return 0

    cache_dir = os.getenv('MIKOKUJI_CACHE_DIR') if not default else _DEFAULT_CACHE_DIR
    cache = (cache_dir if cache_dir is not None else _DEFAULT_CACHE_DIR) + xlsx_links[0]

    os.makedirs(os.path.dirname(cache), exist_ok=True)

    if os.path.basename(cache) in os.listdir(os.path.dirname(cache)):
        click.echo('Already updated.')
        return 1

    try:
        with urllib.request.urlopen(DOMAIN + xlsx_links[0]) as web_file:
            data = web_file.read()
            if cache:
                with open(cache, mode='wb') as local_file:
                    local_file.write(data)
            click.echo('Update is done! Cache file at : {}'.format(cache))
            return 1

    except urllib.error.URLError as e:
        print(e)
        return 0


@cmd.command()
def clean():
    """キャッシュをゴミ箱に移動します"""

    user_cache_dir = os.getenv('MIKOKUJI_CACHE_DIR')

    if user_cache_dir is not None:
        if os.path.exists(user_cache_dir):
            if not click.confirm('You are using a custom cache directory ({}). Do you want to continue?'.format(user_cache_dir)):
                raise click.Abort()
            send2trash(user_cache_dir)
            click.echo('User cache is moved to Trash.')
        else:
            click.echo('User cache is already cleaned.')

    if os.path.exists(_DEFAULT_CACHE_DIR):
        send2trash(_DEFAULT_CACHE_DIR)
        click.echo('Default cache is moved to Trash.')
    else:
        click.echo('Default cache is already cleaned.')

    click.echo("Cleaning is all done!")

    return 1


def parse_xlsx(number, data):

    df = pd.read_excel(data, header=HEADER_ROW)

    kanji1 = int2kanji(int(number))
    kanji2 = "".join(map(lambda x: '〇一二三四五六七八九'[int(x)], str(number)))

    query = ""
    for c in [str(number), kanji1, kanji2]:
        query = query + c + "|"
    query = query.rstrip('|')

    rd = df[df[Header.number].str.contains(query, na=False)]

    return rd


if __name__ == "__main__":
    cmd()
