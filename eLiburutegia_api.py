import requests
from bs4 import BeautifulSoup
import re
from enum import Enum
import os
import markdownify
import unicodedata
import io
import requests

class DownloadStatus(Enum):
    SUCCESS = 1
    GENERIC_ERROR = -1
    FILE_NOT_FOUND = -2
    LENGTH_ERROR = -3
class session:
    usercookie: str
    sessionid: str
    language: str

    def __init__(self, usercookie, sessionid, language):
        self.usercookie = usercookie
        self.sessionid = sessionid
        self.language = language

class book:
    id: int
    name: str
    author: str
    sinopsis: str

    def __init__(self, id, name, author, sinopsis):
        self.id = id
        self.name = name
        self.author = author
        self.sinopsis = sinopsis

BASE_URL = "https://www.euskadi.eus/ac37aELiburutegiaPublicaWar/home/maint?locale=eu"
SEARCH_URL = 'https://www.euskadi.eus/ac37aELiburutegiaPublicaWar/buscar?locale=eu&formato=1|200|2|201|7|20'
BOOK_URL_BASE = "https://www.euskadi.eus/ac37aELiburutegiaPublicaWar/libro/"
COVER_URL_BASE = "https://www.euskadi.eus/ac37aELiburutegiaPublicaWar/fichero/getPortada"
STREAMING_URL_BASE = "https://www.euskadi.eus/ac37aELiburutegiaPublicaWar/streaming/"

basic_headers = {
    'Host': 'www.euskadi.eus',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
    'Accept': '*/*',
    'Accept-Language': 'eu,en-US;q=0.7,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin'
}

def normalize_filename(filename):
    filename = unicodedata.normalize("NFC", filename)
    filename = re.sub(r'[\\/:*?"<>|]', "-", filename)
    filename = filename.strip()
    return filename

# Function to make a GET request to a URL
def make_get_request(url: str, headers: dict[str, str] = None) -> requests.Response:
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an error for bad status codes (4xx, 5xx)
        return response
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

# Function to make a HEAD request to a URL
def make_head_request(url: str, headers: dict[str, str] = None) -> requests.structures.CaseInsensitiveDict[str]:
    try:
        response = requests.head(url, headers=headers)
        response.raise_for_status()  # Raises an error for bad status codes (4xx, 5xx)
        return response.headers
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

# Function to get the initial cookies from the response
def get_header_cookies(response: requests.Response) -> session:
    usercookie = None
    sessionid = None
    language = None

    for cookie in response.cookies:
        if cookie.name == 'r01euskadiUserCookie':
            usercookie = cookie.value
        elif cookie.name == 'JSESSIONID':
            sessionid = cookie.value
        elif cookie.name == 'language':
            language = cookie.value
    return session(usercookie, sessionid, language)

# 1. Hasierako cookieak lortu
def init_session() -> session:
    response = make_get_request(BASE_URL)
    return get_header_cookies(response)

# 1.5 Liburuak bilatu
def search_book_basic(search_term: str, page: int = 1, input_search_url = SEARCH_URL) -> tuple[list[book], int]:
    search_url = input_search_url + '&termino=' + search_term
    if page > 1:
        search_url += f"&iPageNo={page}"
    response = make_get_request(search_url)

    soup = BeautifulSoup(response.text, 'html.parser')
    results_count_text = soup.find('p', class_='search__count').text.strip()
    results_count = int(re.search(r'(\d{1,3}(?:,\d{3})*)', results_count_text).group(1).replace(',', ''))

    # Extract the details of each book
    books = []
    book_elements = soup.find_all('li', class_='book-wrapper')
    for book_element in book_elements:
        id = book_element.find('div', class_='book')['id']
        title = book_element.find('p', class_='book__title').text.strip()
        author = book_element.find('p', class_='book__author').text.strip().split('\r')[0]
        author = ' '.join(author.split(', ')[::-1])
        sinopsis = markdownify.markdownify(book_element.find('div', class_='book__sinopsis')['data-sinopsis']).replace('**', '').strip()
        books.append(book(id, title, author, sinopsis))

    return books, results_count

# 2. Streaming url lortu
def get_epub_url(book_id: int, home_session: session) -> tuple[str, session]:
    headers = basic_headers.copy()
    headers['Cookie'] = f'r01euskadiUserCookie={home_session.usercookie}; r01euskadiCookie=webopd00_eu; JSESSIONID={home_session.sessionid}; language={home_session.language}'
    streaming_url = STREAMING_URL_BASE + book_id
    response = make_get_request(streaming_url, headers)

    # Hurrengoan erabiltzeko Cookieak lortu
    cookies_streaming = get_header_cookies(response)
    # Epub url lortu
    soup = BeautifulSoup(response.text, 'html.parser')
    script_tag = soup.find('script', string=re.compile(r'var epubUrl'))
    epub_url_match = re.search(r"var epubUrl='(.*?)';", script_tag.string)
    if epub_url_match:
        epub_url = epub_url_match.group(1)
    else:
        epub_url = None
    return epub_url, cookies_streaming

# 3. Epub fitxategia lortu
def obtain_epub_content(book_url: str, streaming_session: session) -> bytes:
    resultContent = None
    headers = basic_headers.copy()
    headers['Cookie'] = f'r01euskadiUserCookie={streaming_session.usercookie}; r01euskadiCookie=webopd00_eu; JSESSIONID={streaming_session.sessionid}; language={streaming_session.language}'
    # Obtain the number of bytes to download the entire file
    num_bytes = int(make_head_request(book_url, headers).get('Content-Length'))

    if num_bytes > 0:
        headers['Range'] = f'bytes=0-{num_bytes-1}'
        epub_response = make_get_request(book_url, headers)
        resultContent = epub_response.content

    return resultContent

def download_id_to_buffer(book_id: int, buffer: io.BytesIO) -> DownloadStatus:
    home_session = init_session()
    first_book_url, streaming_session = get_epub_url(book_id, home_session)

    download_content = obtain_epub_content(first_book_url, streaming_session)
    if download_content is None:
        return DownloadStatus.FILE_NOT_FOUND
    buffer.write(download_content)
    return DownloadStatus.SUCCESS

def download_to_disk(book: book, home_session = None, download_folder: str = "downloads") -> int:
    if home_session is None:
        home_session = init_session()
    first_book_url, streaming_session = get_epub_url(book.id, home_session)
    filename = f"{book.author} - {book.name} ({book.id})"
    output_file_path = f"{download_folder}/{normalize_filename(filename)}.epub"
    if os.path.exists(output_file_path):
        return 1 # File already exists

    epub_content = obtain_epub_content(first_book_url, streaming_session)
    if epub_content is not None:
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        with open(output_file_path, 'wb') as f:
            f.write(epub_content)
        return 0 # Success
    return -1 # Generic error
